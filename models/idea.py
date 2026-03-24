from pydantic import BaseModel, Field


class Idea(BaseModel):
    # Source paper reference
    paper_title: str
    paper_summary: str
    paper_link: str

    # LLM-extracted fields
    key_idea: str
    methods: str
    agent_relevance: bool
    tags: list[str] = Field(default_factory=list)

    # Set by analysis agent
    novelty_score: float = 0.0
    novelty_label: str = "unknown"  # "novel" | "incremental" | "unknown"
