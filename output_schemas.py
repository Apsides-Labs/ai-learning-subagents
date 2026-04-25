from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    """Base for all LLM output schemas — rejects extra fields from LLM."""
    model_config = ConfigDict(extra="forbid")


class CompetitorOutput(_StrictModel):
    name: str
    url: str
    positioning: str
    target_audience: str
    content_gaps: list[str]


class ContentOpportunityOutput(_StrictModel):
    angle: str
    rationale: str
    target_audience: str


class ProductFactOutput(_StrictModel):
    fact: str
    source_file: str


class ArticlePlanOutput(_StrictModel):
    id: str
    title: str
    primary_keyword: str
    secondary_keywords: list[str]
    search_intent: str
    article_type: str
    target_audience: str
    angle: str
    meta_description: str
    suggested_headings: list[str]
    cta_prompt: str


class SEOOutput(_StrictModel):
    articles: list[ArticlePlanOutput]


class ArticleOutput(_StrictModel):
    title: str
    primary_keyword: str
    meta_description: str
    markdown_content: str


class FactCheckItemOutput(_StrictModel):
    claim: str
    verdict: str
    source_sentence: str


class FactCheckOutput(_StrictModel):
    passed: bool
    items: list[FactCheckItemOutput]


class ResearchSetupOutput(_StrictModel):
    product_facts: list[ProductFactOutput]
    competitors: list[CompetitorOutput]


class MarketBriefOutput(_StrictModel):
    pain_points: list[str]
    content_opportunities: list[ContentOpportunityOutput]
