from pydantic import BaseModel


class Competitor(BaseModel):
    name: str
    url: str
    positioning: str
    target_audience: str
    content_gaps: list[str] = []


class ProductFact(BaseModel):
    fact: str
    source_file: str


class ContentOpportunity(BaseModel):
    angle: str
    rationale: str
    target_audience: str


class ResearchBrief(BaseModel):
    competitors: list[Competitor] = []
    pain_points: list[str] = []
    content_opportunities: list[ContentOpportunity] = []
