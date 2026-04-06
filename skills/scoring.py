"""Multi-factor scoring system for ideas.

final_score = W_NOVELTY * novelty + W_RELEVANCE * relevance + W_REPO_READINESS * repo_readiness
"""

from __future__ import annotations

import re
from typing import Any

import config
from models.idea import Idea
from utils.helpers import cosine_similarity
from utils.llm_client import LLMClient


# ---------------------------------------------------------------------------
# Jaccard helpers (moved from tools/memory_tool.py)
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "is", "for", "with",
    "on", "that", "this", "we", "our", "by",
    # High-frequency domain terms that cause false similarity
    "financial", "market", "model", "data", "system", "approach",
    "method", "based", "using", "learning", "network",
}


def _word_set(text: str) -> set[str]:
    """Lowercase word set, stripping punctuation."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _jaccard_similarity(new_key_idea: str, past_ideas: list[dict]) -> float:
    """Max Jaccard similarity between new idea and past ideas."""
    if not past_ideas:
        return 0.0

    new_words = _word_set(new_key_idea)
    if not new_words:
        return 0.0

    max_sim = 0.0
    for past in past_ideas:
        past_words = _word_set(past.get("key_idea", ""))
        if not past_words:
            continue
        intersection = len(new_words & past_words)
        union = len(new_words | past_words)
        sim = intersection / union if union else 0.0
        max_sim = max(max_sim, sim)

    return max_sim


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run(state: dict[str, Any]) -> dict[str, Any]:
    """Score all ideas in state and select top picks."""
    ideas = state.get("ideas", [])
    repo_results = state.get("repo_results", [])
    past_ideas = state.get("iteration_context", {}).get("past_ideas", [])
    llm: LLMClient | None = state.get("_llm_fixed")

    # Batch-embed for semantic novelty
    idea_embeddings, past_embeddings = await _batch_embed_novelty(
        ideas, past_ideas, llm
    )

    scored = []
    for idx, idea in enumerate(ideas):
        idea_emb = idea_embeddings[idx] if idea_embeddings else None
        scored_idea = score_idea(
            idea, repo_results, past_ideas,
            idea_emb=idea_emb, past_embs=past_embeddings,
        )
        scored.append(scored_idea)

    scored.sort(key=lambda i: i.final_score, reverse=True)
    selected = scored[:2]
    print(f"------------> \nscored ")
    for s in scored:
        print(f"{getattr(s, 'key_idea', '')[:60]}... - final: {getattr(s, 'final_score', 0):.2f}, "
              f"novelty: {getattr(s, 'novelty_score', 0):.2f}, "
              f"relevance: {getattr(s, 'relevance_score', 0):.2f}, "
              f"repo_readiness: {getattr(s, 'repo_readiness_score', 0):.2f}")
    return {"scored_ideas": scored, "selected_ideas": selected}


def score_idea(
    idea: Idea,
    repo_results: list[dict[str, Any]],
    past_ideas: list[dict],
    *,
    idea_emb: list[float] | None = None,
    past_embs: list[list[float]] | None = None,
) -> Idea:
    """Compute all sub-scores and final_score, updating the Idea in place."""

    # --- Novelty (hybrid: semantic + Jaccard) ---
    jaccard_sim = _jaccard_similarity(idea.key_idea, past_ideas)

    if idea_emb and past_embs:
        semantic_sim = max(
            cosine_similarity(idea_emb, pe) for pe in past_embs
        )
        # Hybrid: 60% semantic, 40% Jaccard
        combined_sim = 0.6 * semantic_sim + 0.4 * jaccard_sim
    else:
        # Fallback: Jaccard only
        combined_sim = jaccard_sim

    idea.novelty_score = 1.0 - combined_sim

    # --- Relevance (keyword match against domain keywords) ---
    idea.relevance_score = _compute_relevance(idea)

    # --- Repo readiness (combined leverage + feasibility) ---
    idea.repo_readiness_score = _compute_repo_readiness(idea, repo_results)

    # --- Final weighted score ---
    idea.final_score = (
        config.WEIGHT_NOVELTY * idea.novelty_score
        + config.WEIGHT_RELEVANCE * idea.relevance_score
        + config.WEIGHT_REPO_READINESS * idea.repo_readiness_score
    )

    return idea


# ---------------------------------------------------------------------------
# Sub-score functions
# ---------------------------------------------------------------------------

def _compute_relevance(idea: Idea) -> float:
    """Score 0-1 based on keyword overlap with AGENT_KEYWORDS."""
    text = (idea.key_idea + " " + idea.methods + " " + " ".join(idea.tags)).lower()
    matches = sum(1 for kw in config.AGENT_KEYWORDS if kw in text)
    return min(matches / 3.0, 1.0)


def _compute_repo_readiness(idea: Idea, repo_results: list[dict[str, Any]]) -> float:
    """Score 0-1 based on repo quality signals.

    For GitHub-sourced ideas, looks up the source repo directly.
    For arXiv ideas, matches via keyword overlap.
    """
    if not repo_results:
        return 0.0

    repo = _find_matching_repo(idea, repo_results)
    if repo is None:
        return 0.0

    return _score_repo_quality(repo)


def _find_matching_repo(
    idea: Idea, repo_results: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Find the repo associated with an idea."""
    # GitHub ideas: match by source URL
    if idea.source == "github" and idea.source_link:
        for repo in repo_results:
            if repo.get("url", "") == idea.source_link:
                return repo

    # arXiv ideas (or GitHub with no URL match): keyword overlap
    idea_words = set(idea.key_idea.lower().split()) | {t.lower() for t in idea.tags}
    best_repo = None
    best_overlap = 0
    for repo in repo_results:
        desc = (repo.get("description", "") + " " + repo.get("readme", "")).lower()
        overlap = sum(1 for w in idea_words if w in desc)
        if overlap > best_overlap:
            best_overlap = overlap
            best_repo = repo

    return best_repo


def _score_repo_quality(repo: dict[str, Any]) -> float:
    """Score a repo on quality signals (0-1). No star count."""
    score = 0.0
    readme = repo.get("readme", "").lower()
    files = repo.get("files", [])
    files_lower = [f.lower() for f in files]

    # Framework / entry point
    if "streamlit" in readme or "fastapi" in readme:
        score += 0.25
    elif "main.py" in files_lower or "app.py" in files_lower:
        score += 0.25

    # Dependency management
    if "requirements.txt" in files or "pyproject.toml" in files:
        score += 0.25

    # Examples / demos
    if any(f in ("examples", "example", "demo", "demos") for f in files_lower):
        score += 0.25

    # Documentation depth
    if len(repo.get("readme", "")) > 500:
        score += 0.25

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

async def _batch_embed_novelty(
    ideas: list[Idea],
    past_ideas: list[dict],
    llm: LLMClient | None,
) -> tuple[list[list[float]], list[list[float]]]:
    """Batch-embed current and past idea texts. Returns (idea_embs, past_embs).

    Returns empty lists on failure (triggers Jaccard-only fallback).
    """
    if not llm or not ideas or not past_ideas:
        return [], []

    current_texts = [idea.key_idea for idea in ideas]
    past_texts = [p.get("key_idea", "") for p in past_ideas]
    all_texts = current_texts + past_texts

    try:
        all_embeddings = await llm.embed(all_texts)
    except Exception:
        return [], []

    n_current = len(current_texts)
    return all_embeddings[:n_current], all_embeddings[n_current:]
