"""Shared agent state — the single mutable object passed through the agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Statuses — used across plan, steps, and phases. Named constants to avoid
# magic strings while staying dict-compatible with the state object.
# ---------------------------------------------------------------------------
PENDING = "pending"
EXECUTING = "executing"
OK = "ok"
FAILED = "failed"
SKIPPED = "skipped"
NEEDS_REPLAN = "needs_replan"
DONE = "done"


@dataclass
class PlanStep:
    """A single step in the agent plan."""
    action: str
    input: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    status: str = PENDING

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_initial_state(goal: str) -> dict[str, Any]:
    """Return a fresh state dict for a new agent run."""
    return {
        "goal": goal,
        "ideas": [],
        "repo_results": [],
        "papers": [],
        "scored_ideas": [],
        "selected_ideas": [],
        "proposals": [],
        "plan": {
            "steps": [],           # list[PlanStep]
            "current_index": 0,
            "status": PENDING,
        },
        "iteration_context": {
            "previous_failures": [],
            "strategy_adjustment": "",
            "past_ideas": [],  # past ideas loaded from memory DB (capped)
        },
        "quality_signals": {
            "ideas_strength": "unknown",   # weak | strong
            "novelty": "unknown",          # low | high
        },
        "evaluation": {},
        "tool_call_log": [],
        "timing": {
            "cycles": [],  # list[{"cycle", "plan_ms", "execute_ms", "critique_ms", "total_ms"}]
            "steps": [],   # list[{"step", "action", "duration_ms"}]
        },
    }


def update_state(
    state: dict[str, Any],
    tool_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Merge tool output into shared state.

    Each tool returns a dict whose keys match top-level state keys.
    Lists are extended (not replaced); dicts are merged; scalars are overwritten.
    """
    for key, value in result.items():
        if key not in state:
            state[key] = value
        elif isinstance(state[key], list) and isinstance(value, list):
            state[key].extend(value)
        elif isinstance(state[key], dict) and isinstance(value, dict):
            state[key].update(value)
        else:
            state[key] = value
    return state


def state_summary(state: dict[str, Any]) -> str:
    """Return a concise text summary of current state for the LLM decision prompt."""
    lines = [f"Goal: {state['goal']}"]
    lines.append(f"Papers fetched: {len(state['papers'])}")
    lines.append(f"Ideas extracted: {len(state['ideas'])}")
    lines.append(f"GitHub repos found: {len(state['repo_results'])}")
    lines.append(f"Scored ideas: {len(state['scored_ideas'])}")
    lines.append(f"Selected ideas: {len(state['selected_ideas'])}")
    lines.append(f"Proposals generated: {len(state['proposals'])}")
    lines.append(f"Tool calls so far: {len(state['tool_call_log'])}")

    plan = state.get("plan", {})
    if plan.get("steps"):
        completed = sum(1 for s in plan["steps"] if s.status == DONE)
        lines.append(f"Plan status: {plan.get('status', PENDING)}")
        lines.append(f"Plan steps: {completed}/{len(plan['steps'])}")

    cycle_timings = state.get("timing", {}).get("cycles", [])
    if cycle_timings:
        last = cycle_timings[-1]
        lines.append(
            f"Last cycle latency: {last['total_ms']}ms "
            f"(plan: {last['plan_ms']}, execute: {last['execute_ms']}, "
            f"critique: {last['critique_ms']})"
        )

    ctx = state.get("iteration_context", {})
    if ctx.get("strategy_adjustment"):
        lines.append(f"Strategy adjustment: {ctx['strategy_adjustment']}")
    if ctx.get("previous_failures"):
        lines.append(f"Previous failures: {', '.join(ctx['previous_failures'])}")
    if ctx.get("past_ideas"):
        lines.append(f"Past ideas loaded: {len(ctx['past_ideas'])}")

    return "\n".join(lines)
