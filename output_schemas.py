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


class PainPointOutput(_StrictModel):
    statement: str
    sources: list[str]
    intensity: str          # low | medium | high
    frequency: str          # isolated | recurring | dominant
    content_addressable: bool


class ContentOpportunityOutput(_StrictModel):
    angle: str
    addresses_pain_point: str   # reference to the pain point statement this addresses
    competitor_gap: str         # competitor name whose gap this fills, or "none"
    why_now: str
    article_type_hint: str      # standard | topic_teaser


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
    blog_category: str


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
    crawl_failures: list[str] = []
    coverage_note: str = ""


class MarketBriefOutput(_StrictModel):
    pain_points: list[PainPointOutput]
    content_opportunities: list[ContentOpportunityOutput]
    tensions: list[str] = []
    data_coverage_note: str = ""
