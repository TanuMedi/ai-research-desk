"""Blog tool — fetch curated AI blog posts and extract techniques + use cases."""

from __future__ import annotations

import re
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# MCP-style schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "blog_search",
    "description": "Fetch recent posts from curated AI blogs (OpenAI, Anthropic, LangChain) and extract techniques and use cases.",
    "input_schema": {
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Keywords to filter blog posts (e.g. ['agent', 'tool-use'])",
        },
        "sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Blog RSS/Atom feed URLs to fetch. Uses defaults if empty.",
        },
    },
    "use_when": "You need practical techniques, product announcements, or industry trends from AI company blogs.",
    "produces": ["blog_posts"],
}

# Default curated feeds
DEFAULT_FEEDS = [
    "https://blog.openai.com/rss/",
    "https://www.anthropic.com/rss.xml",
    "https://blog.langchain.dev/rss/",
]


async def run(tool_input: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point."""
    keywords = tool_input.get("keywords", [])
    sources = tool_input.get("sources", []) or DEFAULT_FEEDS
    posts = await fetch_blog_posts(sources, keywords)
    return {"blog_posts": posts}


async def fetch_blog_posts(
    feed_urls: list[str],
    keywords: list[str] | None = None,
) -> list[dict[str, str]]:
    """Fetch and parse RSS/Atom feeds, optionally filtering by keywords."""
    posts: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for url in feed_urls:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                parsed = _parse_feed_xml(resp.text, source=url)
                posts.extend(parsed)
            except httpx.HTTPError:
                continue

    if keywords:
        kw_lower = [k.lower() for k in keywords]
        posts = [
            p for p in posts
            if any(
                kw in p.get("title", "").lower() or kw in p.get("summary", "").lower()
                for kw in kw_lower
            )
        ]

    return posts


def _parse_feed_xml(xml_text: str, source: str) -> list[dict[str, str]]:
    """Lightweight RSS/Atom parser using regex (avoids extra dependencies)."""
    posts: list[dict[str, str]] = []

    # Try RSS <item> blocks first
    items = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
    if not items:
        # Try Atom <entry> blocks
        items = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)

    for item in items[:15]:  # cap at 15 per feed
        title = _extract_tag(item, "title")
        link = _extract_tag(item, "link")
        # Atom uses <link href="..."/>
        if not link:
            link_match = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', item)
            link = link_match.group(1) if link_match else ""
        summary = _extract_tag(item, "description") or _extract_tag(item, "summary") or ""
        # Strip HTML tags from summary
        summary = re.sub(r"<[^>]+>", "", summary).strip()[:500]
        pub_date = _extract_tag(item, "pubDate") or _extract_tag(item, "published") or ""

        posts.append({
            "title": title,
            "link": link,
            "summary": summary,
            "published": pub_date,
            "source": source,
        })

    return posts


def _extract_tag(text: str, tag: str) -> str:
    """Extract text content from an XML tag."""
    # Handle CDATA
    match = re.search(
        rf"<{tag}[^>]*>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{tag}>",
        text,
        re.DOTALL,
    )
    return match.group(1).strip() if match else ""
