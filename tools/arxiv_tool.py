import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import arxiv

import config
from models.paper import Paper
from utils.llm_client import LLMClient
from utils.summarizer import summarize_papers_batch

# ---------------------------------------------------------------------------
# MCP-style schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "arxiv_search",
    "description": "Fetch recent cs.AI papers from arXiv and summarize them via LLM to extract ideas.",
    "input_schema": {
        "query": {"type": "string", "description": "arXiv query (default: cat:cs.AI)"},
        "max_results": {"type": "integer", "description": "Max papers to fetch (default: 30)"},
    },
    "use_when": "You need academic research papers, novel techniques, or state-of-the-art methods.",
    "produces": ["papers", "ideas"],
}


async def run(tool_input: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point: fetch papers, keyword-filter, summarize."""
    query = tool_input.get("query", config.ARXIV_QUERY)
    max_results = tool_input.get("max_results", config.MAX_PAPERS)

    papers = await fetch_recent_papers(query=query, max_results=max_results)

    # Keyword pre-filter
    keywords = config.AGENT_KEYWORDS
    filtered = [
        p for p in papers
        if any(kw in p.summary.lower() or kw in p.title.lower() for kw in keywords)
    ]

    # Summarize via LLM (needs llm from state)
    llm: LLMClient = state.get("_llm_fixed")
    ideas = []
    if llm and filtered:
        ideas = await summarize_papers_batch(filtered, llm)
        ideas = [i for i in ideas if i.agent_relevance]

    return {"papers": [p.model_dump() for p in papers], "ideas": ideas}


# ---------------------------------------------------------------------------
# Core functions (unchanged, reused by the wrapper above)
# ---------------------------------------------------------------------------

async def fetch_recent_papers(
    query: str = None,
    max_results: int = None,
) -> list[Paper]:
    """Fetch up to max_results recent cs.AI papers from the last DAYS_LOOKBACK days."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _fetch_sync, query or config.ARXIV_QUERY, max_results or config.MAX_PAPERS
    )


def _fetch_sync(query: str, max_results: int) -> list[Paper]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.DAYS_LOOKBACK)

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers: list[Paper] = []
    client = arxiv.Client()
    for result in client.results(search):
        published = result.published
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published < cutoff:
            break
        papers.append(
            Paper(
                title=result.title.strip(),
                authors=[a.name for a in result.authors],
                summary=result.summary.strip(),
                link=result.entry_id,
                published=published,
            )
        )

    return papers
