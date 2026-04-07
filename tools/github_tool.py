"""GitHub tool — search repos and return structured metadata."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

import config
from models.repo import Repo

# ---------------------------------------------------------------------------
# MCP-style schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "github_search",
    "description": "Search GitHub for trending AI repositories created in the last 7 days. Returns structured repo metadata.",
    "input_schema": {
        "query": {"type": "string", "description": "GitHub search query (e.g. 'fintech llm agent')"},
        "max_results": {"type": "integer", "description": "Max repos to return (default: 10)"},
    },
    "use_when": "You need real-world implementations, reusable code, or leverage scores for ideas.",
    "produces": ["repo_results"],
}

_GITHUB_API = "https://api.github.com"


async def run(tool_input: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point. Returns structured repo metadata only — no idea generation."""
    query = tool_input.get("query", "")
    max_results = tool_input.get("max_results", 10)
    repos = await search_repos(query, max_results)

    return {
        "repo_results": [r.model_dump() for r in repos],
    }


async def search_repos(query: str, max_results: int = 10) -> list[Repo]:
    """Search GitHub for trending AI repos created in the last DAYS_LOOKBACK days."""
    headers = _auth_headers()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=config.DAYS_LOOKBACK)).strftime("%Y-%m-%d")
    ai_topics = " ".join([
        "topic:llm", "topic:ai", "topic:machine-learning",
        "topic:deep-learning", "topic:generative-ai", "topic:nlp",
    ])
    trending_query = f"{query} {ai_topics} created:>{cutoff}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GITHUB_API}/search/repositories",
            params={"q": trending_query, "sort": "stars", "order": "desc", "per_page": max_results},
            headers=headers,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])

        results: list[Repo] = []
        for item in items:
            full_name = item["full_name"]
            description = item.get("description", "") or ""
            files: list[str] = []
            readme = ""

            # Fetch file list (root level)
            try:
                contents_resp = await client.get(
                    f"{_GITHUB_API}/repos/{full_name}/contents",
                    headers=headers,
                )
                if contents_resp.status_code == 200:
                    files = [f["name"] for f in contents_resp.json() if isinstance(f, dict)]
            except httpx.HTTPError:
                pass

            # Fetch README
            try:
                readme_resp = await client.get(
                    f"{_GITHUB_API}/repos/{full_name}/readme",
                    headers=headers,
                )
                if readme_resp.status_code == 200:
                    content = readme_resp.json().get("content", "")
                    readme = base64.b64decode(content).decode("utf-8", errors="replace")[:2000]
            except httpx.HTTPError:
                pass

            repo = Repo(
                full_name=full_name,
                description=description,
                stars=item.get("stargazers_count", 0),
                language=item.get("language", ""),
                url=item.get("html_url", ""),
                topics=item.get("topics", []),
                readme=readme,
                files=files,
                created_at=item.get("created_at", ""),
                updated_at=item.get("updated_at", "")
            )
            results.append(repo)

        return results


def _auth_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
