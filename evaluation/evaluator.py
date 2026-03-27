"""Evaluation framework — measures idea quality, proposal quality, and tool efficiency."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import config
from utils.llm_client import LLMClient
from utils.prompts import EVALUATE_IDEA_PROMPT, EVALUATE_PROPOSAL_PROMPT


async def evaluate_run(state: dict[str, Any], llm: LLMClient) -> dict[str, Any]:
    """Run all evaluations and return a summary dict."""
    evaluation = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "idea_quality": await _score_ideas(state.get("scored_ideas", []), llm),
        "proposal_quality": await _score_proposals(state.get("proposals", []), llm),
        "tool_efficiency": _compute_efficiency(state),
    }

    # Save to file
    _save_evaluation(evaluation)
    return evaluation


async def _score_ideas(ideas: list, llm: LLMClient) -> dict[str, Any]:
    """Use LLM-as-judge to rate ideas on actionability, novelty, usefulness."""
    if not ideas:
        return {"average": 0, "details": []}

    details = []
    for idea in ideas[:5]:  # cap at 5 to limit LLM calls
        prompt = EVALUATE_IDEA_PROMPT.format(
            key_idea=getattr(idea, "key_idea", ""),
            methods=getattr(idea, "methods", ""),
            tags=", ".join(getattr(idea, "tags", [])),
        )
        try:
            raw = await llm.complete(prompt)
            scores = _parse_json(raw)
            avg = sum(scores.values()) / len(scores) if scores else 0
            details.append({"idea": getattr(idea, "source_title", ""), "scores": scores, "average": round(avg, 1)})
        except Exception:
            details.append({"idea": getattr(idea, "source_title", ""), "scores": {}, "average": 0})

    overall = sum(d["average"] for d in details) / len(details) if details else 0
    return {"average": round(overall, 1), "details": details}


async def _score_proposals(proposals: list, llm: LLMClient) -> dict[str, Any]:
    """Use LLM-as-judge to rate proposals on clarity, feasibility, completeness."""
    if not proposals:
        return {"average": 0, "details": []}

    details = []
    for proposal in proposals:
        prompt = EVALUATE_PROPOSAL_PROMPT.format(
            idea_title=getattr(proposal, "idea_title", ""),
            why_it_matters=getattr(proposal, "why_it_matters", ""),
            demo_scope=getattr(proposal, "demo_scope", ""),
            data_requirements=getattr(proposal, "data_requirements", ""),
        )
        try:
            raw = await llm.complete(prompt)
            scores = _parse_json(raw)
            avg = sum(scores.values()) / len(scores) if scores else 0
            details.append({"proposal": getattr(proposal, "idea_title", ""), "scores": scores, "average": round(avg, 1)})
        except Exception:
            details.append({"proposal": getattr(proposal, "idea_title", ""), "scores": {}, "average": 0})

    overall = sum(d["average"] for d in details) / len(details) if details else 0
    return {"average": round(overall, 1), "details": details}


def _compute_efficiency(state: dict[str, Any]) -> dict[str, Any]:
    """Compute tool call efficiency metrics."""
    log = state.get("tool_call_log", [])
    total = len(log)
    successful = sum(1 for entry in log if entry.get("success", False))
    failed = total - successful

    # Detect redundant calls (same tool + same input)
    seen: set[str] = set()
    redundant = 0
    for entry in log:
        key = f"{entry['tool']}:{json.dumps(entry.get('input', {}), sort_keys=True)}"
        if key in seen:
            redundant += 1
        seen.add(key)

    efficiency = successful / total if total > 0 else 0

    return {
        "total_calls": total,
        "successful_calls": successful,
        "failed_calls": failed,
        "redundant_calls": redundant,
        "efficiency_ratio": round(efficiency, 2),
    }


def _save_evaluation(evaluation: dict[str, Any]) -> None:
    """Save evaluation results to storage/logs/eval_<timestamp>.json."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(config.LOG_DIR, f"eval_{ts}.json")
    with open(path, "w") as f:
        json.dump(evaluation, f, indent=2, default=str)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)
