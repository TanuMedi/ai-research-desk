from pydantic import BaseModel


class Proposal(BaseModel):
    idea_title: str
    why_it_matters: str
    demo_scope: str
    data_requirements: str
