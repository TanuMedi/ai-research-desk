"""Core agent loop — plan → execute → critique cycle."""

from __future__ import annotations

import json
import time
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


async def run_agent(
    goal: str,
    llm: LLMClient,
    registry: ToolRegistry,
) -> dict[str, Any]:
    """Run the agent through plan → execute → critique cycles.

    Workflow:
      1. Load past ideas from memory DB for novelty comparison.
      2. For each cycle (up to config.MAX_CYCLES):
         a. PLAN  — LLM generates an ordered list of PlanSteps from the
            current state, goal, available tools, and past ideas.
         b. EXECUTE — each PlanStep is dispatched to the appropriate tool
            or skill; state is updated after each step. Failures are
            caught per-step and logged; the phase is marked FAILED only
            if any step fails.
         c. CRITIQUE — if execution succeeded and proposals were produced,
            the critic agent reviews them. If improvements are needed,
            the cycle repeats with updated iteration_context
            (strategy_adjustment, failures).
      3. Store this run's ideas back to memory DB.
      4. Return final state including timing data for all cycles and steps.

    Demos are generated separately in main.py after user approval.
    """
    state = create_initial_state(goal)
    state["_llm"] = llm

    # await _load_past_ideas(registry, state)

    agent_start = time.perf_counter()

    for cycle in range(1, config.MAX_CYCLES + 1):
        console.print(f"\n[bold magenta]━━━ Cycle {cycle}/{config.MAX_CYCLES} ━━━[/bold magenta]")
        cycle_timing = await _run_cycle(cycle, goal, state, registry, llm)
        state["timing"]["cycles"].append(cycle_timing)
        _print_cycle_timing(cycle, cycle_timing)

        if state["plan"]["status"] != NEEDS_REPLAN:
            break
    # await call_tool(registry, "memory", {"action": "store"}, state)

    total_time_ms = int((time.perf_counter() - agent_start) * 1000)
    console.print(f"\n[bold green]✓ Agent finished in {total_time_ms}ms[/bold green]")

    state.pop("_llm", None)
    return state


# ---------------------------------------------------------------------------
# Cycle phases
# ---------------------------------------------------------------------------

async def _run_cycle(
    cycle: int,
    goal: str,
    state: dict[str, Any],
    registry: ToolRegistry,
    llm: LLMClient,
) -> dict[str, Any]:
    """Execute one plan → execute → critique cycle. Returns timing record."""
    cycle_start = time.perf_counter()
    phase_results = {
        "plan": PENDING,
        "execute": PENDING,
        "critique": PENDING,
    }

    # Phase 1: Plan
    plan_ms, plan_ok = await _phase_plan(goal, state, registry, llm)
    phase_results["plan"] = OK if plan_ok else FAILED

    # Phase 2: Execute
    execute_ms = 0
    if plan_ok:
        execute_ms, execute_status = await _phase_execute(state, registry)
        phase_results["execute"] = execute_status
    else:
        phase_results["execute"] = SKIPPED

    # Phase 3: Critique — only runs if execute succeeded
    critique_ms, critique_status = await _phase_critique(state, phase_results["execute"])
    phase_results["critique"] = critique_status

    total_ms = int((time.perf_counter() - cycle_start) * 1000)
    return {
        "cycle": cycle,
        "plan_ms": plan_ms,
        "execute_ms": execute_ms,
        "critique_ms": critique_ms,
        "total_ms": total_ms,
        "phase_results": phase_results,
    }


async def _phase_plan(
    goal: str,
    state: dict[str, Any],
    registry: ToolRegistry,
    llm: LLMClient,
) -> tuple[int, bool]:
    """Generate a plan. Returns (duration_ms, success)."""
    start = time.perf_counter()
    plan = await generate_plan(goal, state, registry, llm)
    ms = int((time.perf_counter() - start) * 1000)

    if not plan.get("steps"):
        console.print("  [yellow]Planner returned no steps — stopping[/yellow]")
        return ms, False

    steps = [
        PlanStep(
            action=s.get("action", ""),
            input=s.get("input", {}),
            reasoning=s.get("reasoning", ""),
        )
        for s in plan["steps"]
    ]
    print(f"--------> Generated plan steps: \n{steps} <------")

    state["plan"] = {"steps": steps, "current_index": 0, "status": EXECUTING}
    console.print(f"  [cyan]Plan: {len(steps)} steps[/cyan] [dim]({ms}ms)[/dim]")
    return ms, True


SKILL_ACTIONS = {"score_ideas", "generate_proposals"}


async def _phase_execute(
    state: dict[str, Any],
    registry: ToolRegistry,
) -> tuple[int, str]:
    """Execute plan steps. Returns (duration_ms, status).

    After github_search completes, execution pauses and returns
    NEEDS_REPLAN so the planner can re-evaluate with updated state —
    e.g. skip arXiv if GitHub already produced enough ideas.

    Status is FAILED if any step fails, NEEDS_REPLAN if paused after
    github_search, OK if all steps completed.
    """
    start = time.perf_counter()
    steps: list[PlanStep] = state["plan"]["steps"]
    failures = 0
    github_executed = False

    for i, plan_step in enumerate(steps):
        # Pause after github_search — replan to reassess before more tools/skills
        if github_executed:
            remaining = len(steps) - i
            console.print(
                f"\n  [dim]Pausing after github_search ({remaining} steps remaining) "
                f"— replanning with updated state[/dim]"
            )
            for s in steps[i:]:
                s.status = SKIPPED
            ms = int((time.perf_counter() - start) * 1000)
            return ms, NEEDS_REPLAN

        state["plan"]["current_index"] = i
        console.print(f"\n  [bold cyan]Step {i + 1}/{len(steps)}:[/bold cyan] {plan_step.action}")
        console.print(f"    [dim]{plan_step.reasoning}[/dim]")

        step_start = time.perf_counter()
        result = await execute_step(plan_step, registry, state)
        step_ms = int((time.perf_counter() - step_start) * 1000)

        state["timing"]["steps"].append({
            "step": i + 1,
            "action": plan_step.action,
            "duration_ms": step_ms,
            "status": FAILED if "error" in result else OK,
        })

        if "error" in result:
            console.print(f"    [red]✗ Error: {result['error']}[/red] [dim]({step_ms}ms)[/dim]")
            plan_step.status = FAILED
            failures += 1
            state["iteration_context"]["previous_failures"].append(
                f"{plan_step.action}: {result['error']}"
            )
        else:
            plan_step.status = DONE
            state = update_state(state, plan_step.action, result)
            result_keys = [k for k in result if k != "error"]
            console.print(f"    [green]✓ Updated: {result_keys}[/green] [dim]({step_ms}ms)[/dim]")

        if plan_step.action == "github_search":
            github_executed = True

    ms = int((time.perf_counter() - start) * 1000)
    if failures > 0:
        label = "all" if failures == len(steps) else "partial"
        console.print(f"    [dim]Execute phase: {failures}/{len(steps)} steps failed ({label})[/dim]")
    return ms, FAILED if failures > 0 else OK


async def _phase_critique(
    state: dict[str, Any],
    execute_status: str,
) -> tuple[int, str]:
    """Run critic if execution produced results. Returns (duration_ms, status)."""
    if execute_status in (FAILED, SKIPPED):
        state["plan"]["status"] = NEEDS_REPLAN
        return 0, SKIPPED

    if not state.get("proposals"):
        state["plan"]["status"] = NEEDS_REPLAN
        return 0, SKIPPED

    console.print("\n  [bold yellow]Running critic...[/bold yellow]")
    start = time.perf_counter()
    critique_result = await run_critic_agent(state)
    ms = int((time.perf_counter() - start) * 1000)

    if critique_result:
        state.update(update_state(state, "critic", critique_result))

    strategy = critique_result.get("iteration_context", {}).get(
        "strategy_adjustment", ""
    )
    if strategy:
        console.print(f"    [yellow]Critic requests replan:[/yellow] {strategy}")
        state["plan"]["status"] = NEEDS_REPLAN
        return ms, NEEDS_REPLAN

    console.print(f"    [green]✓ Critic approved[/green] [dim]({ms}ms)[/dim]")
    state["plan"]["status"] = DONE
    return ms, OK


# ---------------------------------------------------------------------------
# Helpers
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
        f"\n  [dim]Cycle {cycle}: plan {timing['plan_ms']}ms | "
        f"execute {timing['execute_ms']}ms | critique {timing['critique_ms']}ms | "
        f"total {timing['total_ms']}ms[/dim]"
    )


async def generate_plan(
    goal: str,
    state: dict[str, Any],
    registry: ToolRegistry,
    llm: LLMClient,
) -> dict[str, Any]:
    """Ask the LLM to generate a multi-step plan."""
    past_ideas = state.get("iteration_context", {}).get("past_ideas", [])
    # Cap to avoid bloating the prompt; see config for rationale
    capped = past_ideas[:config.MAX_PAST_IDEAS_FOR_PLANNING]
    past_ideas_summary = json.dumps(capped, indent=2) if capped else "None"
    print(f"--------> state summary for planner: \n{state_summary(state)} <------")
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


