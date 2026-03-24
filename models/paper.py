from datetime import datetime
from pydantic import BaseModel


class Paper(BaseModel):
    title: str
    authors: list[str]
    summary: str
    link: str
    published: datetime
