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
