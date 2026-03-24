import asyncio
import json

from models.idea import Idea
from models.paper import Paper
from utils.llm_client import LLMClient
from utils.prompts import SUMMARIZE_PAPER_PROMPT


async def summarize_paper(paper: Paper, llm: LLMClient) -> Idea | None:
    """Summarize a single paper via LLM. Returns None if parsing fails after retry."""
    prompt = SUMMARIZE_PAPER_PROMPT.format(
        title=paper.title,
        abstract=paper.summary,
    )

    for attempt in range(2):
        try:
            raw = await llm.complete(prompt if attempt == 0 else prompt + "\nIMPORTANT: Return ONLY a raw JSON object. No markdown, no backticks, no explanation.")
            parsed = _parse_json(raw)
            return Idea(
                paper_title=paper.title,
                paper_summary=paper.summary,
                paper_link=paper.link,
                key_idea=parsed.get("key_idea", ""),
                methods=parsed.get("methods", ""),
                agent_relevance=bool(parsed.get("agent_relevance", False)),
                tags=parsed.get("tags", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt == 1:
                return None
    return None


async def summarize_papers_batch(papers: list[Paper], llm: LLMClient) -> list[Idea]:
    """Concurrently summarize all papers, dropping any that fail."""
    results = await asyncio.gather(*[summarize_paper(p, llm) for p in papers])
    return [r for r in results if r is not None]


def _parse_json(text: str) -> dict:
    """Strip markdown fences if present, then parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first and last fence lines
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)
