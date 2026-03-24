import asyncio
from datetime import datetime, timedelta, timezone

import arxiv

import config
from models.paper import Paper


async def fetch_recent_papers() -> list[Paper]:
    """Fetch up to MAX_PAPERS recent cs.AI papers from the last DAYS_LOOKBACK days."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _fetch_sync)
    return results


def _fetch_sync() -> list[Paper]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.DAYS_LOOKBACK)

    search = arxiv.Search(
        query=config.ARXIV_QUERY,
        max_results=config.MAX_PAPERS,
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
