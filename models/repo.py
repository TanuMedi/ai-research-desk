from pydantic import BaseModel, Field


class Repo(BaseModel):
    full_name: str
    description: str
    url: str
    stars: int = 0
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    readme: str = ""
    files: list[str] = Field(default_factory=list)
    leverage_score: float = 0.0
