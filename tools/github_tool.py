"""GitHub tool — search repos and extract metadata."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

import config
from models.repo import Repo
from utils.llm_client import LLMClient
from utils.summarizer import summarize_repos_batch

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
    "produces": ["repo_results", "ideas"],
}

_GITHUB_API = "https://api.github.com"


async def run(tool_input: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point."""
    query = tool_input.get("query", "")
    max_results = tool_input.get("max_results", 10)
    repos = await search_repos(query, max_results)

    # Summarize repos into Ideas via LLM
    llm: LLMClient = state.get("_llm_fixed")
    ideas = []
    if llm and repos:
        ideas = await summarize_repos_batch(repos, llm)
        ideas = [i for i in ideas if i.agent_relevance]

    return {
        "repo_results": [r.model_dump() for r in repos],
        "ideas": ideas,
    }


async def search_repos(query: str, max_results: int = 10) -> list[Repo]:
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
                language=item.get("language", "") or "",
                url=item.get("html_url", ""),
                topics=item.get("topics", []),
                readme=readme,
                files=files,
            )
            results.append(repo)

        return results


def _auth_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
