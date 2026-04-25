import pytest
from models.article import ArticleStatus, ArticleType, ContentCalendarEntry
from models.research import Competitor, ProductFact, ContentOpportunity, ResearchBrief
from models.seo import KeywordData, ArticlePlan


def test_content_calendar_entry_defaults():
    entry = ContentCalendarEntry(
        id="test-slug",
        title="How to Learn Anything Fast",
        primary_keyword="learn anything fast",
        article_type=ArticleType.standard,
        target_audience="curious learners",
        angle="timeframe personalisation beats generic courses",
        meta_description="A 150-char meta description.",
        cta_prompt="",
    )
    assert entry.status == ArticleStatus.planned
    assert entry.secondary_keywords == []
    assert entry.suggested_headings == []
    assert entry.draft_path is None


def test_content_calendar_entry_status_progression():
    entry = ContentCalendarEntry(
        id="slug",
        title="T",
        primary_keyword="kw",
        article_type=ArticleType.topic_teaser,
        target_audience="a",
        angle="b",
        meta_description="c",
        cta_prompt="prompt",
    )
    assert entry.status == ArticleStatus.planned
    entry.status = ArticleStatus.in_progress
    assert entry.status == ArticleStatus.in_progress


def test_research_brief_defaults():
    brief = ResearchBrief()
    assert brief.competitors == []
    assert brief.pain_points == []
    assert brief.content_opportunities == []


def test_competitor_model():
    c = Competitor(
        name="Duolingo",
        url="https://duolingo.com",
        positioning="gamified language learning",
        target_audience="casual language learners",
        content_gaps=["personalised timeframes", "non-language topics"],
    )
    assert c.name == "Duolingo"
    assert len(c.content_gaps) == 2


def test_keyword_data_model():
    kw = KeywordData(
        keyword="how to learn Spanish in 30 days",
        intent="informational",
        competition_level="low",
        trend="rising",
    )
    assert kw.competition_level == "low"


def test_article_plan_round_trips_to_dict():
    plan = ArticlePlan(
        id="learn-spanish-30-days",
        title="How to Learn Spanish in 30 Days",
        primary_keyword="learn Spanish fast",
        secondary_keywords=["Spanish for beginners"],
        search_intent="informational",
        article_type="topic_teaser",
        target_audience="beginners",
        angle="Draft and Arc generates a personalised Spanish course in seconds",
        meta_description="Learn Spanish in 30 days with a personalised plan.",
        suggested_headings=["H2: Why 30 days works", "H2: The plan"],
        cta_prompt="Create a 30-day beginner Spanish course for me",
    )
    d = plan.model_dump()
    assert d["id"] == "learn-spanish-30-days"
    ArticlePlan(**d)  # round-trips without error


from output_schemas import (
    _StrictModel,
    CompetitorOutput,
    ContentOpportunityOutput,
    ProductFactOutput,
    ResearchSetupOutput,
    MarketBriefOutput,
    ArticlePlanOutput,
    SEOOutput,
    ArticleOutput,
    FactCheckItemOutput,
    FactCheckOutput,
)


def test_strict_model_rejects_extra_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CompetitorOutput(
            name="X",
            url="https://x.com",
            positioning="p",
            target_audience="a",
            content_gaps=[],
            unexpected_field="boom",
        )


def test_research_setup_output_valid():
    output = ResearchSetupOutput(
        competitors=[
            CompetitorOutput(
                name="Duolingo",
                url="https://duolingo.com",
                positioning="gamified",
                target_audience="casual",
                content_gaps=["no custom topics"],
            )
        ],
        product_facts=[
            ProductFactOutput(
                fact="Users set daily learning time",
                source_file="app/models/course.py",
            )
        ],
    )
    assert len(output.competitors) == 1
    assert len(output.product_facts) == 1
    assert output.crawl_failures == []
    assert output.coverage_note == ""


def test_research_setup_output_with_failures():
    output = ResearchSetupOutput(
        product_facts=[],
        competitors=[],
        crawl_failures=["https://arist.co — returned 403"],
        coverage_note="Only app/models/ was available; app/ai/ not included in gathered data.",
    )
    assert len(output.crawl_failures) == 1
    assert "403" in output.crawl_failures[0]
    assert output.coverage_note != ""


def test_market_brief_output_valid():
    output = MarketBriefOutput(
        pain_points=["no personalised pacing"],
        content_opportunities=[
            ContentOpportunityOutput(
                angle="Feynman technique for programmers",
                rationale="competitors don't cover this",
                target_audience="developers",
            )
        ],
    )
    assert len(output.pain_points) == 1
    assert len(output.content_opportunities) == 1


def test_fact_check_output_passed():
    fc = FactCheckOutput(passed=True, items=[])
    assert fc.passed


def test_fact_check_output_flagged():
    fc = FactCheckOutput(
        passed=False,
        items=[
            FactCheckItemOutput(
                claim="Draft and Arc offers video lessons",
                verdict="UNSUPPORTED",
                source_sentence="Draft and Arc offers video lessons for visual learners.",
            )
        ],
    )
    assert not fc.passed
    assert fc.items[0].verdict == "UNSUPPORTED"
