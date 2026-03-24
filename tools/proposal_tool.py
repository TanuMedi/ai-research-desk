import json

from models.idea import Idea
from models.proposal import Proposal
from utils.llm_client import LLMClient
from utils.prompts import GENERATE_PROPOSAL_PROMPT


async def generate_proposal(idea: Idea, llm: LLMClient) -> Proposal:
    """Generate a demo proposal for a given idea via LLM."""
    prompt = GENERATE_PROPOSAL_PROMPT.format(
        idea_title=idea.paper_title,
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
            parsed = _parse_json(raw)
            return Proposal(
                idea_title=parsed.get("idea_title", idea.paper_title),
                why_it_matters=parsed.get("why_it_matters", ""),
                novelty=parsed.get("novelty", ""),
                demo_scope=parsed.get("demo_scope", ""),
                data_requirements=parsed.get("data_requirements", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt == 1:
                # Fallback: return a minimal proposal
                return Proposal(
                    idea_title=idea.paper_title,
                    why_it_matters=idea.key_idea,
                    novelty=idea.novelty_label,
                    demo_scope="To be defined.",
                    data_requirements="To be defined.",
                )
    return Proposal(
        idea_title=idea.paper_title,
        why_it_matters=idea.key_idea,
        novelty=idea.novelty_label,
        demo_scope="To be defined.",
        data_requirements="To be defined.",
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)
