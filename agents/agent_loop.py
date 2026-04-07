"""Core agent loop — initialization phase + refinement loop."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from agents.critic_agent import run_critic_agent
import config
from executor.state_manager import (
    PlanStep,
    create_initial_state,
    state_summary,
    update_state,
    PENDING, EXECUTING, OK, FAILED, SKIPPED, NEEDS_REPLAN, DONE,
)
from executor.tool_executor import call_tool
from skills.scoring import run as run_scoring
from skills.proposal_generation import run as run_proposals
from tools.registry import ToolRegistry
from utils.llm_client import LLMClient, parse_llm_json
from utils.prompts import PLANNER_PROMPT

console = Console()

# ---------------------------------------------------------------------------
# Proposal-level statuses
# ---------------------------------------------------------------------------
ACCEPT = "ACCEPT"
REVISE = "REVISE"
REPLACE = "REPLACE"
REJECT = "REJECT"

# Cap on total proposal replacements across all cycles
MAX_REPLACEMENTS = 2
# Minimum accepted proposals before we can stop early
MIN_ACCEPTABLE = 1


@dataclass
class PlannerDecision:
    """A planner decision for a single proposal."""
    proposal_index: int
    action: str          # "rewrite_proposal" | "replace_proposal" | "retrieve_more_data"
    reasoning: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 1: Initialization (runs once)
# ---------------------------------------------------------------------------

async def run_init_phase(
    goal: str,
    llms: dict[str, LLMClient],
    registry: ToolRegistry,
) -> dict[str, Any]:
    """Deterministic initialization: parallel retrieval, scoring, initial proposals.

    No LLM planning — just fetch from all sources, score, and generate proposals.
    """
    state = create_initial_state(goal)
    state["_llm_fixed"] = llms["fixed"]
    state["_llm_low"] = llms["low"]
    state["_llm_high"] = llms["high"]

    console.print("\n[bold cyan]━━━ Init Phase ━━━[/bold cyan]")
    init_start = time.perf_counter()

    # --- Parallel retrieval from all sources ---
    console.print("  [cyan]Fetching from all sources in parallel...[/cyan]")
    retrieval_results = await asyncio.gather(
        call_tool(registry, "arxiv_search", {}, state),
        call_tool(registry, "github_search", {"query": "AI agent"}, state),
        return_exceptions=True,
    )

    source_names = ["arxiv_search", "github_search"]
    for name, result in zip(source_names, retrieval_results):
        if isinstance(result, Exception):
            console.print(f"    [red]✗ {name} failed: {result}[/red]")
        elif "error" in result:
            console.print(f"    [red]✗ {name} error: {result['error']}[/red]")
        else:
            state = update_state(state, name, result)
            console.print(f"    [green]✓ {name} returned data[/green]")

    ideas_count = len(state.get("ideas", []))
    if ideas_count == 0:
        console.print("  [red]No ideas extracted from any source.[/red]")
        raise RuntimeError("Init phase produced no ideas — cannot continue.")

    console.print(f"  [green]Total ideas extracted: {ideas_count}[/green]")

    # --- Score ideas ---
    console.print("  [cyan]Scoring ideas...[/cyan]")
    score_result = await run_scoring(state)
    state = update_state(state, "score_ideas", score_result)
    console.print(f"  [green]✓ Scored {len(state.get('scored_ideas', []))} ideas, "
                  f"selected top {len(state.get('selected_ideas', []))}[/green]")

    # --- Generate initial proposals ---
    console.print("  [cyan]Generating initial proposals...[/cyan]")
    proposal_result = await run_proposals(state)
    state = update_state(state, "generate_proposals", proposal_result)
    proposals = state.get("proposals", [])
    console.print(f"  [green]✓ Generated {len(proposals)} proposals[/green]")

    # --- Initialize per-proposal statuses ---
    state["proposal_statuses"] = {i: PENDING for i in range(len(proposals))}

    init_ms = int((time.perf_counter() - init_start) * 1000)
    state["timing"]["init_ms"] = init_ms
    console.print(f"  [dim]Init phase completed in {init_ms}ms[/dim]")

    return state


# ---------------------------------------------------------------------------
# Phase 2: Refinement loop
# ---------------------------------------------------------------------------

async def run_agent_loop(
    state: dict[str, Any],
    registry: ToolRegistry,
) -> dict[str, Any]:
    """Run the refinement loop: critic → planner → executor per cycle.

    Converges when at least MIN_ACCEPTABLE proposals are ACCEPTED
    and no proposal needs further work, or MAX_CYCLES is reached.
    """
    console.print("\n[bold magenta]━━━ Refinement Loop ━━━[/bold magenta]")
    loop_start = time.perf_counter()
    total_replacements = 0

    for cycle in range(1, config.MAX_CYCLES + 1):
        console.print(f"\n  [bold magenta]── Cycle {cycle}/{config.MAX_CYCLES} ──[/bold magenta]")
        cycle_start = time.perf_counter()

        # --- Step 1: Critique current proposals ---
        critique_ms = await _phase_critique(state)

        # --- Check convergence ---
        statuses = state["proposal_statuses"]
        accepted = sum(1 for s in statuses.values() if s == ACCEPT)
        needs_work = any(s in (REVISE, REPLACE) for s in statuses.values())

        console.print(f"    [dim]Statuses: {dict(statuses)} "
                      f"(accepted={accepted}, needs_work={needs_work})[/dim]")

        if accepted >= MIN_ACCEPTABLE and not needs_work:
            console.print(f"  [green]✓ Converged: {accepted} proposals accepted[/green]")
            break

        # --- Step 2: Plan per-proposal decisions ---
        decisions = _make_planner_decisions(state, total_replacements)
        if not decisions:
            console.print("  [yellow]No actionable decisions — stopping[/yellow]")
            break

        for d in decisions:
            console.print(f"    [cyan]Proposal {d.proposal_index}: {d.action}[/cyan] "
                          f"[dim]({d.reasoning})[/dim]")

        # --- Step 3: Execute decisions ---
        exec_replacements = await _execute_decisions(decisions, state, registry)
        total_replacements += exec_replacements

        cycle_ms = int((time.perf_counter() - cycle_start) * 1000)
        state["timing"]["cycles"].append({
            "cycle": cycle,
            "critique_ms": critique_ms,
            "total_ms": cycle_ms,
        })

    total_ms = int((time.perf_counter() - loop_start) * 1000)
    state["timing"]["loop_ms"] = total_ms
    console.print(f"\n[bold green]✓ Refinement loop finished in {total_ms}ms[/bold green]")

    # Clean up internal LLM references
    state.pop("_llm_low", None)
    state.pop("_llm_fixed", None)
    state.pop("_llm_high", None)
    return state


# ---------------------------------------------------------------------------
# Critique phase
# ---------------------------------------------------------------------------

async def _phase_critique(state: dict[str, Any]) -> int:
    """Run critic on current proposals and update per-proposal statuses.

    Returns duration in ms.
    """
    proposals = state.get("proposals", [])
    if not proposals:
        console.print("    [yellow]No proposals to critique[/yellow]")
        return 0

    console.print("    [yellow]Running critic...[/yellow]")
    start = time.perf_counter()
    critique_result = await run_critic_agent(state)
    ms = int((time.perf_counter() - start) * 1000)

    # Map existing critic output to per-proposal statuses.
    # Current critic returns {"needs_improvement": bool, "issues": [...], "suggestions": [...]}
    # via apply_critique_to_state which wraps in iteration_context.
    # TODO: later, critic should return per-proposal verdicts with action type
    # (rewrite_only, needs_more_data, replace_proposal)
    if critique_result.get("iteration_context", {}).get("strategy_adjustment"):
        # Critic found issues — mark all non-accepted proposals as REVISE
        for i, status in state["proposal_statuses"].items():
            if status not in (ACCEPT, REJECT):
                state["proposal_statuses"][i] = REVISE
        console.print(f"    [yellow]Critic requests revisions[/yellow] [dim]({ms}ms)[/dim]")
    else:
        # Critic approved — mark all pending proposals as ACCEPT
        for i, status in state["proposal_statuses"].items():
            if status not in (ACCEPT, REJECT):
                state["proposal_statuses"][i] = ACCEPT
        console.print(f"    [green]✓ Critic approved[/green] [dim]({ms}ms)[/dim]")

    return ms


# ---------------------------------------------------------------------------
# Planner phase — deterministic decisions based on critic output
# ---------------------------------------------------------------------------

def _make_planner_decisions(
    state: dict[str, Any],
    total_replacements: int,
) -> list[PlannerDecision]:
    """Create a PlannerDecision for each non-accepted, non-rejected proposal.

    TODO: update planner prompt later to support per-proposal LLM decisions.
    For now, decisions are derived from proposal statuses set by the critic.
    """
    decisions: list[PlannerDecision] = []
    statuses = state["proposal_statuses"]

    for i, status in statuses.items():
        if status in (ACCEPT, REJECT):
            continue

        if status == REPLACE:
            if total_replacements >= MAX_REPLACEMENTS:
                statuses[i] = REJECT
                console.print(f"    [dim]Proposal {i}: replacement cap reached, rejecting[/dim]")
                continue
            decisions.append(PlannerDecision(
                proposal_index=i,
                action="replace_proposal",
                reasoning="Critic marked for replacement",
            ))
        elif status == REVISE:
            decisions.append(PlannerDecision(
                proposal_index=i,
                action="rewrite_proposal",
                reasoning="Critic requested revisions",
            ))
        else:
            # PENDING or unknown — default to rewrite
            decisions.append(PlannerDecision(
                proposal_index=i,
                action="rewrite_proposal",
                reasoning="Proposal pending review, attempting rewrite",
            ))

    return decisions


# ---------------------------------------------------------------------------
# Execute phase — deterministic dispatch per decision
# ---------------------------------------------------------------------------

async def _execute_decisions(
    decisions: list[PlannerDecision],
    state: dict[str, Any],
    registry: ToolRegistry,
) -> int:
    """Execute planner decisions. Returns number of replacements performed."""
    replacements = 0

    for decision in decisions:
        i = decision.proposal_index

        if decision.action == "rewrite_proposal":
            console.print(f"    [cyan]Rewriting proposal {i}...[/cyan]")
            result = await run_proposals(state, idea_indices=[i])
            new_proposals = result.get("proposals", [])
            if new_proposals:
                state["proposals"][i] = new_proposals[0]
                state["proposal_statuses"][i] = PENDING
                console.print(f"    [green]✓ Proposal {i} rewritten[/green]")
            else:
                state["proposal_statuses"][i] = REJECT
                console.print(f"    [red]✗ Proposal {i} rewrite failed, rejecting[/red]")

        elif decision.action == "replace_proposal":
            console.print(f"    [cyan]Replacing proposal {i}...[/cyan]")
            replaced = _replace_with_next_idea(i, state)
            if not replaced:
                state["proposal_statuses"][i] = REJECT
                console.print(f"    [red]✗ No more scored ideas for replacement, rejecting[/red]")
                continue
            # Generate a new proposal for the replacement idea
            result = await run_proposals(state, idea_indices=[i])
            new_proposals = result.get("proposals", [])
            if new_proposals:
                state["proposals"][i] = new_proposals[0]
                state["proposal_statuses"][i] = PENDING
                replacements += 1
                console.print(f"    [green]✓ Proposal {i} replaced with new idea[/green]")
            else:
                state["proposal_statuses"][i] = REJECT
                console.print(f"    [red]✗ Proposal generation failed after replacement, rejecting[/red]")

        elif decision.action == "retrieve_more_data":
            console.print(f"    [cyan]Retrieving more data for proposal {i}...[/cyan]")
            tool_name = decision.tool_input.get("tool", "github_search")
            tool_input = decision.tool_input.get("input", {})
            result = await call_tool(registry, tool_name, tool_input, state)
            if "error" in result:
                state["proposal_statuses"][i] = REJECT
                console.print(f"    [red]✗ Retrieval failed: {result['error']}, rejecting[/red]")
                continue
            state = update_state(state, tool_name, result)
            # Re-score with new data
            score_result = await run_scoring(state)
            state = update_state(state, "score_ideas", score_result)
            # Regenerate proposal
            prop_result = await run_proposals(state, idea_indices=[i])
            new_proposals = prop_result.get("proposals", [])
            if new_proposals:
                state["proposals"][i] = new_proposals[0]
                state["proposal_statuses"][i] = PENDING
                console.print(f"    [green]✓ Retrieved, re-scored, regenerated proposal {i}[/green]")
            else:
                state["proposal_statuses"][i] = REJECT
                console.print(f"    [red]✗ Proposal generation failed after retrieval, rejecting[/red]")

    return replacements


def _replace_with_next_idea(
    proposal_index: int,
    state: dict[str, Any],
) -> bool:
    """Swap the idea at proposal_index with the next best scored idea not already selected.

    Updates state["selected_ideas"] in place. Returns True if replacement found.
    """
    scored = state.get("scored_ideas", [])
    selected = state.get("selected_ideas", [])
    selected_titles = {getattr(idea, "source_title", "") for idea in selected}

    for candidate in scored:
        title = getattr(candidate, "source_title", "")
        if title not in selected_titles:
            selected[proposal_index] = candidate
            return True
    return False


# ---------------------------------------------------------------------------
# Helpers (kept from original)
# ---------------------------------------------------------------------------

async def _load_past_ideas(registry: ToolRegistry, state: dict[str, Any]) -> None:
    """Load past ideas from memory DB into state for novelty comparison."""
    console.print("\n[dim]Loading past ideas from memory...[/dim]")
    result = await call_tool(registry, "memory", {"action": "load"}, state)
    past_ideas = result.get("past_ideas", [])
    state["iteration_context"]["past_ideas"] = past_ideas
    console.print(f"  [green]✓ Loaded {len(past_ideas)} past ideas[/green]")


def _print_cycle_timing(cycle: int, timing: dict[str, Any]) -> None:
    console.print(
        f"\n  [dim]Cycle {cycle}: critique {timing.get('critique_ms', 0)}ms | "
        f"total {timing['total_ms']}ms[/dim]"
    )


async def generate_plan(
    goal: str,
    state: dict[str, Any],
    registry: ToolRegistry,
) -> dict[str, Any]:
    """Ask the LLM to generate a multi-step plan.

    TODO: update prompt to support per-proposal refinement decisions.
    Currently kept for potential use in retrieve_more_data decisions.
    """
    llm = state["_llm_low"]
    past_ideas = state.get("iteration_context", {}).get("past_ideas", [])
    capped = past_ideas[:config.MAX_PAST_IDEAS_FOR_PLANNING]
    past_ideas_summary = json.dumps(capped, indent=2) if capped else "None"
    prompt = PLANNER_PROMPT.format(
        goal=goal,
        state_summary=state_summary(state),
        tool_schemas=registry.get_schemas_for_llm(),
        memory_context=past_ideas_summary,
    )

    for attempt in range(2):
        try:
            raw = await llm.complete(
                prompt if attempt == 0
                else prompt + "\nIMPORTANT: Return ONLY a raw JSON object. No markdown, no backticks."
            )
            return parse_llm_json(raw)
        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt == 1:
                return {"steps": []}
    return {"steps": []}


async def execute_step(
    step: PlanStep,
    registry: ToolRegistry,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch a single plan step to the appropriate tool or skill."""
    valid_tool_names = {t.name for t in registry.list_tools()}

    try:
        if step.action == "score_ideas":
            return await run_scoring(state)
        elif step.action == "generate_proposals":
            return await run_proposals(state, idea_indices=step.input.get("idea_indices"))
        elif step.action in valid_tool_names:
            return await call_tool(registry, step.action, step.input, state)
        else:
            return {"error": f"Unknown action: {step.action}"}
    except Exception as exc:
        return {"error": f"{step.action} raised {type(exc).__name__}: {exc}"}
