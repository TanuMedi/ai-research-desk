import asyncio
import json

from models.idea import Idea
from models.paper import Paper
from models.repo import Repo
from utils.llm_client import LLMClient, parse_llm_json
from utils.prompts import IDEA_PROPOSAL_PROMPT


async def summarize_source(
    title: str, summary: str, link: str, source: str, llm: LLMClient,
) -> Idea | None:
    """Summarize a single source (paper or repo) via LLM. Returns None if parsing fails."""
    prompt = IDEA_PROPOSAL_PROMPT.format(title=title, abstract=summary)

    for attempt in range(2):
        try:
            raw = await llm.complete(
                prompt if attempt == 0
                else prompt + "\nIMPORTANT: Return ONLY a raw JSON object. No markdown, no backticks, no explanation."
            )
            parsed = parse_llm_json(raw)
            return Idea(
                source_title=title,
                source_summary=summary,
                source_link=link,
                source=source,
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
    results = await asyncio.gather(*[
        summarize_source(p.title, p.summary, p.link, "arxiv", llm)
        for p in papers
    ])
    return [r for r in results if r is not None]


async def summarize_repos_batch(repos: list[Repo], llm: LLMClient) -> list[Idea]:
    """Concurrently summarize all repos, dropping any that fail."""
    results = await asyncio.gather(*[
        summarize_source(
            r.full_name,
            (r.description + "\n\n" + r.readme[:1500]).strip(),
            r.url,
            "github",
            llm,
        )
        for r in repos
    ])
    return [r for r in results if r is not None]
