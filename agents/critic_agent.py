"""Critic agent — reviews proposals and suggests improvements."""

from __future__ import annotations

import json
from typing import Any

from models.proposal import Proposal
from utils.llm_client import LLMClient, parse_llm_json
from utils.prompts import CRITIC_PROMPT


async def run_critic_agent(state: dict[str, Any]) -> dict[str, Any]:
    llm: LLMClient = state.get("_llm_fixed")
    proposals = state.get("proposals", [])
    scored_ideas = state.get("scored_ideas", [])

    if not llm or not proposals:
        return {}

    critique = await evaluate_proposals(proposals, scored_ideas, llm)

    return apply_critique_to_state(critique)

def apply_critique_to_state(critique: dict[str, Any]) -> dict[str, Any]:
    """Convert critique output into state updates."""
    if not critique.get("needs_improvement"):
        return {
            "iteration_context": {
                "strategy_adjustment": "",
                "previous_failures": [],
            }
        }

    return {
        "iteration_context": {
            "strategy_adjustment": "; ".join(critique.get("suggestions", [])),
            "previous_failures": critique.get("issues", []),
        },
        # Force regeneration
        "proposals": [],
    }

async def evaluate_proposals(
    proposals: list[Proposal],
    scored_ideas: list,
    llm: LLMClient,
) -> dict[str, Any]:
    """Call LLM to critique proposals."""
    proposals_json = json.dumps(
        [p.model_dump() if hasattr(p, "model_dump") else p for p in proposals],
        indent=2,
    )
    scores_json = json.dumps(
        [
            {
                "title": getattr(i, "source_title", ""),
                "final_score": getattr(i, "final_score", 0),
                "novelty": getattr(i, "novelty_score", 0),
                "leverage": getattr(i, "leverage_score", 0),
            }
            for i in scored_ideas[:len(proposals)]
        ],
        indent=2,
    )

    prompt = CRITIC_PROMPT.format(
        proposals_json=proposals_json,
        scores_json=scores_json,
    )

    for attempt in range(2):
        try:
            raw = await llm.complete(
                prompt if attempt == 0
                else prompt + "\nIMPORTANT: Return ONLY a raw JSON object."
            )
            return parse_llm_json(raw)
        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt == 1:
                return {"needs_improvement": False, "issues": [], "suggestions": []}
    return {"needs_improvement": False, "issues": [], "suggestions": []}

