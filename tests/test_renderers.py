"""Renderer tests. Snapshot-style: feed a known report, check key strings appear."""

from dataclasses import dataclass


def _sample_final_report():
    from models.measurement import (
        FinalMeasurementReport, MeasurementReport, ScoredArticlePerformance, MetricScore,
        GapOpportunity, DataSourceStatus,
    )
    from services.scoring import Label

    report = MeasurementReport(
        window_start="2026-04-21",
        window_end="2026-05-16",
        headline={"articles": 1, "impressions": 800, "clicks": 32, "ctr": 0.04, "avg_position": 12.3},
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
        data_source_status=DataSourceStatus(gsc_ok=True, ga4_ok=True, dfs_ok=True),
    )

    return FinalMeasurementReport(
        report=report,
        actions=[],
        verdicts={"tutorial-hell-progress": "Ranking on page 2 with CTR below expected — title rewrite candidate."},
        coverage_note="GSC, GA4, and DataForSEO all reporting normally.",
    )


def test_measurement_md_includes_terse_per_article_data():
    from renderers.measurement_md import render_md
    md = render_md(_sample_final_report())

    # Header
    assert "Measurement Brief" in md
    assert "2026-04-21" in md
    # Per-article block
    assert "tutorial-hell-progress" in md
    assert "pos 12.3" in md  # raw display, agent reads numbers
    # Verdict
    assert "title rewrite candidate" in md
    # Gap opportunity
    assert "tutorial hell python" in md
    # Coverage
    assert "GSC, GA4, and DataForSEO" in md


def test_measurement_md_omits_glossary_and_score_badges():
    """The agent-facing MD must NOT contain the human-only education."""
    from renderers.measurement_md import render_md
    md = render_md(_sample_final_report())

    assert "Glossary" not in md
    assert "[GOOD]" not in md
    assert "[POOR]" not in md   # raw numbers only, no badges
