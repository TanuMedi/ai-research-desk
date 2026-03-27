from pydantic import BaseModel, Field


class Idea(BaseModel):
    # Source reference (arXiv paper or GitHub repo)
    source_title: str
    source_summary: str
    source_link: str
    source: str = "unknown"  # "arxiv" | "github"

    # LLM-extracted fields
    key_idea: str
    methods: str
    agent_relevance: bool
    tags: list[str] = Field(default_factory=list)

    # Set by analysis / scoring
    novelty_score: float = 0.0
    novelty_label: str = "unknown"  # "novel" | "incremental" | "unknown"
    leverage_score: float = 0.0
    relevance_score: float = 0.0
    feasibility_score: float = 0.0
    final_score: float = 0.0
