import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

import config
from models.idea import Idea
from utils.helpers import current_week_label

# ---------------------------------------------------------------------------
# MCP-style schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "memory",
    "description": "Load past ideas from the SQLite memory DB for novelty comparison, or persist new ideas.",
    "input_schema": {
        "action": {
            "type": "string",
            "enum": ["load", "store"],
            "description": "'load' to fetch past ideas, 'store' to persist current ideas.",
        },
    },
    "use_when": "You need to check idea novelty against past runs or save this week's ideas.",
    "produces": ["past_ideas"],
}


async def run(tool_input: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """MCP-style entry point."""
    action = tool_input.get("action", "load")
    if action == "store":
        ideas = state.get("ideas", [])
        if ideas:
            store_weekly_ideas(ideas)
        return {"stored_count": len(ideas)}
    else:
        weeks_limit = tool_input.get("weeks_limit", config.MEMORY_WEEKS_LIMIT)
        past = get_past_ideas(weeks_limit=weeks_limit)
        return {"past_ideas": past}


def init_db() -> None:
    """Create the ideas table if it doesn't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week TEXT,
                paper_title TEXT,
                paper_link TEXT,
                key_idea TEXT,
                tags TEXT,
                novelty_label TEXT,
                demo_approved INTEGER DEFAULT 0,
                demo_created INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.commit()


def get_past_ideas(weeks_limit: int | None = None) -> list[dict]:
    """Fetch previously stored ideas, optionally capped to the most recent N weeks."""
    with _connect() as conn:
        if weeks_limit and weeks_limit > 0:
            cutoff = _week_label_n_weeks_ago(weeks_limit)
            rows = conn.execute(
                "SELECT paper_title, paper_link, key_idea, tags, novelty_label, demo_approved, demo_created "
                "FROM ideas WHERE week >= ? ORDER BY created_at DESC",
                (cutoff,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT paper_title, paper_link, key_idea, tags, novelty_label, demo_approved, demo_created FROM ideas"
            ).fetchall()
    return [
        {
            "paper_title": r[0],
            "paper_link": r[1],
            "key_idea": r[2],
            "tags": json.loads(r[3]) if r[3] else [],
            "novelty_label": r[4],
            "demo_approved": bool(r[5]),
            "demo_created": bool(r[6]),
        }
        for r in rows
    ]


def store_weekly_ideas(ideas: list[Idea]) -> None:
    """Persist this week's ideas to SQLite (skip duplicates by title+week)."""
    week = current_week_label()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for idea in ideas:
            # Skip if already stored for this week
            exists = conn.execute(
                "SELECT 1 FROM ideas WHERE paper_title = ? AND week = ?",
                (idea.paper_title, week),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO ideas (week, paper_title, paper_link, key_idea, tags, novelty_label, demo_approved, demo_created, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)
                    """,
                    (
                        week,
                        idea.paper_title,
                        idea.paper_link,
                        idea.key_idea,
                        json.dumps(idea.tags),
                        idea.novelty_label,
                        now,
                    ),
                )
        conn.commit()


def mark_demo_approved(paper_titles: list[str]) -> None:
    """Set demo_approved=1 for the given paper titles in the current week."""
    week = current_week_label()
    with _connect() as conn:
        for title in paper_titles:
            conn.execute(
                "UPDATE ideas SET demo_approved = 1 WHERE paper_title = ? AND week = ?",
                (title, week),
            )
        conn.commit()


def classify_novelty(new_idea: Idea, past_ideas: list[dict]) -> tuple[float, str]:
    """
    Compare new_idea against past ideas using Jaccard similarity on word sets.
    Returns (max_similarity_score, "novel" | "incremental").
    """
    if not past_ideas:
        return 0.0, "novel"

    new_words = _word_set(new_idea.key_idea)
    if not new_words:
        return None

    max_sim = 0.0
    for past in past_ideas:
        past_words = _word_set(past.get("key_idea", ""))
        if not past_words:
            continue
        intersection = len(new_words & past_words)
        union = len(new_words | past_words)
        sim = intersection / union if union else 0.0
        max_sim = max(max_sim, sim)

    label = "incremental" if max_sim >= config.NOVELTY_THRESHOLD else "novel"
    return max_sim, label


def _word_set(text: str) -> set[str]:
    """Lowercase word set, stripping punctuation."""
    import re
    words = re.findall(r"[a-z]+", text.lower())
    # Remove common stopwords
    stopwords = {
        "a", "an", "the", "and", "or", "of", "in", "to", "is", "for", "with",
        "on", "that", "this", "we", "our", "by",
        # High-frequency domain terms that cause false similarity
        "financial", "market", "model", "data", "system", "approach",
        "method", "based", "using", "learning", "network",
    }
    return {w for w in words if w not in stopwords and len(w) > 2}


def _week_label_n_weeks_ago(n: int) -> str:
    """Return the week label for N weeks ago, for SQL filtering."""
    from datetime import timedelta
    target = datetime.now(timezone.utc) - timedelta(weeks=n)
    return f"{target.year}-{target.strftime('%b')}-W{target.isocalendar().week:02d}"


def _connect() -> sqlite3.Connection:
    import os
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    return sqlite3.connect(config.DB_PATH)
