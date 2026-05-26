"""Tests for the deterministic measurement dataclasses + url normalization
+ report_to_synthesis_input helper."""


def test_normalize_url_strips_query_and_fragment():
    from models.measurement import normalize_url
    assert normalize_url("https://www.draftandarc.com/blog/foo/?utm=x#a") == \
        "https://www.draftandarc.com/blog/foo"


def test_normalize_url_strips_trailing_slash():
    from models.measurement import normalize_url
    assert normalize_url("https://www.draftandarc.com/blog/foo/") == \
        "https://www.draftandarc.com/blog/foo"


def test_normalize_url_lowercases_host():
    from models.measurement import normalize_url
    assert normalize_url("https://WWW.DraftAndArc.com/blog/Foo") == \
        "https://www.draftandarc.com/blog/Foo"


def test_normalize_url_returns_empty_on_empty():
    from models.measurement import normalize_url
    assert normalize_url("") == ""
    assert normalize_url(None) == ""


def test_report_to_synthesis_input_includes_per_article_data():
    from models.measurement import (
        MeasurementReport, ScoredArticlePerformance, MetricScore,
        GapOpportunity, DataSourceStatus, report_to_synthesis_input,
    )
    from services.scoring import Label

    report = MeasurementReport(
        window_start="2026-04-21",
        window_end="2026-05-16",
        headline={"articles": 1, "impressions": 800, "clicks": 32},
        per_article=[
            ScoredArticlePerformance(
                article_id="tutorial-hell-progress",
                url="https://www.draftandarc.com/blog/tutorial-hell-progress",
                published_at="2026-04-27",
                days_since_publish=22,
                overall_label=Label.borderline,
                metrics={
                    "position": MetricScore(value=12.3, display="pos 12.3", label=Label.poor, reason="page 2"),
                    "ctr": MetricScore(value=0.04, display="4.0%", label=Label.poor, reason="below expected"),
                },
                top_queries=[],
            )
        ],
        gap_opportunities=[
            GapOpportunity(keyword="tutorial hell python", position=28.0, volume=90, url="..."),
        ],
        data_source_status=DataSourceStatus(gsc_ok=True, ga4_ok=True, dfs_ok=True, notes=[]),
    )

    text = report_to_synthesis_input(report)
    assert "tutorial-hell-progress" in text
    assert "12.3" in text
    assert "tutorial hell python" in text
    assert "Window: 2026-04-21 to 2026-05-16" in text
