from pydantic import BaseModel


class KeywordData(BaseModel):
    keyword: str
    intent: str
    competition_level: str  # low | medium | high
    trend: str              # rising | stable | falling


class ArticlePlan(BaseModel):
    id: str
    title: str
    primary_keyword: str
    secondary_keywords: list[str] = []
    search_intent: str = "informational"
    article_type: str
    target_audience: str
    angle: str
    meta_description: str
    suggested_headings: list[str] = []
    cta_prompt: str = ""
