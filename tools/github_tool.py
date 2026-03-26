"""GitHub tool — search repos, extract metadata, compute leverage score."""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx

import config

# ---------------------------------------------------------------------------
# MCP-style schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "github_search",
    "description": "Search GitHub repositories for applied AI implementations. Extracts README, file list, stars, and computes a leverage score.",
    "input_schema": {
        "query": {"type": "string", "description": "GitHub search query (e.g. 'fintech llm agent')"},
        "max_results": {"type": "integer", "description": "Max repos to return (default: 10)"},
    },
    "use_when": "You need real-world implementations, reusable code, or leverage scores for ideas.",
    "produces": ["repo_results"],
}

_GITHUB_API = "https://api.github.com"


async def run(tool_input: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point."""
    query = tool_input.get("query", "")
    max_results = tool_input.get("max_results", 10)
    repos = await search_repos(query, max_results)
    return {"repo_results": repos}


async def search_repos(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search GitHub and return enriched repo metadata."""
    headers = _auth_headers()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GITHUB_API}/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": max_results},
            headers=headers,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])

        results: list[dict[str, Any]] = []
        for item in items:
            repo = {
                "full_name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "url": item.get("html_url", ""),
                "topics": item.get("topics", []),
                "readme": "",
                "files": [],
            }

            # Fetch file list (root level)
            try:
                contents_resp = await client.get(
                    f"{_GITHUB_API}/repos/{item['full_name']}/contents",
                    headers=headers,
                )
                if contents_resp.status_code == 200:
                    repo["files"] = [f["name"] for f in contents_resp.json() if isinstance(f, dict)]
            except httpx.HTTPError:
                pass

            # Fetch README
            try:
                readme_resp = await client.get(
                    f"{_GITHUB_API}/repos/{item['full_name']}/readme",
                    headers=headers,
                )
                if readme_resp.status_code == 200:
                    content = readme_resp.json().get("content", "")
                    repo["readme"] = base64.b64decode(content).decode("utf-8", errors="replace")[:2000]
            except httpx.HTTPError:
                pass

            repo["leverage_score"] = compute_leverage(repo)
            results.append(repo)

        return results


def compute_leverage(repo: dict[str, Any]) -> float:
    """Compute a 0-1 leverage score based on repo characteristics."""
    score = 0.0
    readme = repo.get("readme", "").lower()

    if "streamlit" in readme:
        score += 0.4
    if "fastapi" in readme:
        score += 0.3
    if "requirements.txt" in repo.get("files", []):
        score += 0.2
    if repo.get("stars", 0) > 500:
        score += 0.1

    return min(score, 1.0)


def _auth_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
