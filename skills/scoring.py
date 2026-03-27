"""Multi-factor scoring system for ideas.

final_score = 0.30 * novelty + 0.30 * leverage + 0.25 * relevance + 0.15 * feasibility
"""

from __future__ import annotations

from typing import Any

import config
from models.idea import Idea
from tools.memory_tool import classify_novelty
from tools.github_tool import compute_leverage

async def run(state: dict[str, Any]) -> dict[str, Any]:
    """Score all ideas in state and select top picks."""
    ideas = state.get("ideas", [])
    repo_results = state.get("repo_results", [])
    past_ideas = state.get("past_ideas", [])

    scored = []
    for idea in ideas:
        scored_idea = score_idea(idea, repo_results, past_ideas)
        scored.append(scored_idea)

    # Sort descending by final_score
    scored.sort(key=lambda i: i.final_score, reverse=True)

    # Select top 2
    selected = scored[:2]

    return {"scored_ideas": scored, "selected_ideas": selected}


def score_idea(
    idea: Idea,
    repo_results: list[dict[str, Any]],
    past_ideas: list[dict],
) -> Idea:
    """Compute all sub-scores and final_score, updating the Idea in place."""
    # --- Novelty (reuse existing Jaccard classifier) ---
    sim_score, label = classify_novelty(idea, past_ideas) or (0.0, "novel")
    idea.novelty_score = 1.0 - sim_score  # invert: lower similarity = higher novelty
    idea.novelty_label = label

    # --- Leverage (match idea keywords against GitHub repos) ---
    idea.leverage_score = _compute_idea_leverage(idea, repo_results)

    # --- Relevance (keyword match against domain keywords) ---
    idea.relevance_score = _compute_relevance(idea)

    # --- Feasibility (based on matched repo completeness) ---
    idea.feasibility_score = _compute_feasibility(idea, repo_results)

    # --- Final weighted score ---
    idea.final_score = (
        0.30 * idea.novelty_score
        + 0.30 * idea.leverage_score
        + 0.25 * idea.relevance_score
        + 0.15 * idea.feasibility_score
    )

    return idea


def _compute_idea_leverage(idea: Idea, repo_results: list[dict[str, Any]]) -> float:
    """Find the best-matching repo for this idea and return its leverage score."""
    if not repo_results:
        return 0.0

    idea_words = set(idea.key_idea.lower().split()) | set(t.lower() for t in idea.tags)
    best = 0.0
    for repo in repo_results:
        desc = (repo.get("description", "") + " " + repo.get("readme", "")).lower()
        overlap = sum(1 for w in idea_words if w in desc)
        if overlap > 0:
            leverage = repo.get("leverage_score", compute_leverage(repo))
            best = max(best, leverage)
    return best


def _compute_relevance(idea: Idea) -> float:
    """Score 0-1 based on keyword overlap with AGENT_KEYWORDS."""
    text = (idea.key_idea + " " + idea.methods + " " + " ".join(idea.tags)).lower()
    matches = sum(1 for kw in config.AGENT_KEYWORDS if kw in text)
    # Normalize: 3+ keyword matches = 1.0
    return min(matches / 3.0, 1.0)


def _compute_feasibility(idea: Idea, repo_results: list[dict[str, Any]]) -> float:
    """Estimate feasibility from matching repo completeness signals."""
    if not repo_results:
        return 0.3  # baseline feasibility without repo evidence

    idea_words = set(idea.key_idea.lower().split())
    best = 0.3
    for repo in repo_results:
        desc = (repo.get("description", "") + " " + repo.get("readme", "")).lower()
        if not any(w in desc for w in idea_words):
            continue
        score = 0.3  # baseline
        files = repo.get("files", [])
        if "requirements.txt" in files or "pyproject.toml" in files:
            score += 0.25
        if any(f.lower() in ("examples", "example", "demo", "demos") for f in files):
            score += 0.25
        readme = repo.get("readme", "")
        if len(readme) > 500:
            score += 0.2
        best = max(best, min(score, 1.0))
    return best
