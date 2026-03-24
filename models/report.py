from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

import config


class RunReport(BaseModel):
    """Collects pipeline stats for logging and monitoring."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Research Agent
    papers_fetched: int = 0
    papers_keyword_matched: int = 0
    papers_summarized: int = 0
    papers_failed_summarization: int = 0

    # Analysis Agent
    past_ideas_in_memory: int = 0
    ideas_skipped_no_key_idea: int = 0
    ideas_novel: int = 0
    ideas_incremental: int = 0

    # PM Agent
    top_picks: list[str] = Field(default_factory=list)
    proposals_generated: int = 0

    # Approval
    proposals_approved: int = 0

    def save(self) -> str:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        path = os.path.join(config.LOG_DIR, f"run_report_{ts}.json")
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)
        return path
