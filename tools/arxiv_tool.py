"""arXiv tool — fetch recent papers and return structured metadata."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import arxiv

import config
from models.paper import Paper

# ---------------------------------------------------------------------------
# MCP-style schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "arxiv_search",
    "description": "Fetch recent cs.AI papers from arXiv. Returns structured paper metadata.",
    "input_schema": {
        "query": {"type": "string", "description": "arXiv query (default: cat:cs.AI)"},
        "max_results": {"type": "integer", "description": "Max papers to fetch (default: 30)"},
    },
    "use_when": "You need academic research papers, novel techniques, or state-of-the-art methods.",
    "produces": ["papers"],
}


async def run(tool_input: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point. Returns structured paper metadata."""
    query = tool_input.get("query", config.ARXIV_QUERY)
    max_results = tool_input.get("max_results", config.MAX_PAPERS)

    papers = await fetch_recent_papers(query=query, max_results=max_results)

    # Keyword pre-filter
    keywords = config.AGENT_KEYWORDS
    filtered = [
        p for p in papers
        if any(kw in p.summary.lower() or kw in p.title.lower() for kw in keywords)
    ]

    return {"papers": [p.model_dump() for p in filtered]}


# ---------------------------------------------------------------------------
# Core fetch
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

        # Infer tags from title keywords
        title_lower = result.title.lower()
        tags = [kw for kw in config.AGENT_KEYWORDS if kw in title_lower or kw in result.summary.lower()]

        # Short summary: first sentence of abstract
        abstract = result.summary.strip()
        first_sentence_end = abstract.find(". ")

        papers.append(
            Paper(
                title=result.title.strip(),
                authors=[a.name for a in result.authors],
                summary=abstract,
                link=result.entry_id,
                published=published,
                tags=tags
            )
        )

    return papers