from datetime import datetime
from pydantic import BaseModel, Field


class Paper(BaseModel):
    title: str
    authors: list[str]
    summary: str
    link: str
    published: datetime
    tags: list[str] = Field(default_factory=list)
