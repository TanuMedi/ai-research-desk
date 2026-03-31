import asyncio
import json
from typing import Any

from models.idea import Idea
from models.proposal import Proposal
from utils.llm_client import LLMClient, parse_llm_json
from utils.prompts import GENERATE_PROPOSAL_PROMPT

async def run(state: dict[str, Any], idea_indices: list[int] | None = None) -> dict[str, Any]:
    """Generate proposals for selected ideas."""
    llm: LLMClient = state.get("_llm_high")
    selected = state.get("selected_ideas", [])
    indices = idea_indices or []

    if indices:
        ideas_to_process = [selected[i] for i in indices if i < len(selected)]
    else:
        ideas_to_process = selected

    if not ideas_to_process or not llm:
        return {"proposals": []}

    proposals = await asyncio.gather(
        *[generate_proposal(idea, llm) for idea in ideas_to_process]
    )
    return {"proposals": list(proposals)}


async def generate_proposal(idea: Idea, llm: LLMClient) -> Proposal:
    """Generate a demo proposal for a given idea via LLM."""
    prompt = GENERATE_PROPOSAL_PROMPT.format(
        idea_title=idea.source_title,
        key_idea=idea.key_idea,
        methods=idea.methods,
        tags=", ".join(idea.tags),
        novelty_label=idea.novelty_label,
    )

    for attempt in range(2):
        try:
            raw = await llm.complete(
                prompt if attempt == 0
                else prompt + "\nIMPORTANT: Return ONLY a raw JSON object. No markdown, no backticks."
            )
            parsed = parse_llm_json(raw)
            return Proposal(
                idea_title=parsed.get("idea_title", idea.source_title),
                why_it_matters=parsed.get("why_it_matters", ""),
                novelty=parsed.get("novelty", ""),
                demo_scope=parsed.get("demo_scope", ""),
                data_requirements=parsed.get("data_requirements", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt == 1:
                # Fallback: return a minimal proposal
                return Proposal(
                    idea_title=idea.source_title,
                    why_it_matters=idea.key_idea,
                    novelty=idea.novelty_label,
                    demo_scope="To be defined.",
                    data_requirements="To be defined.",
                )
    return Proposal(
        idea_title=idea.source_title,
        why_it_matters=idea.key_idea,
        novelty=idea.novelty_label,
        demo_scope="To be defined.",
        data_requirements="To be defined.",
    )
