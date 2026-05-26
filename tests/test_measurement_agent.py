"""End-to-end measurement agent. All external clients mocked at the boundary."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_run_measure_assembles_full_report():
    """Full pipeline: GSC + GA4 + DFS Labs → report → render. LLM synthesis mocked."""
    from agents import measurement_agent
    from models.article import ContentCalendarEntry, ArticleStatus, ArticleType
    from output_schemas import MeasurementBriefOutput, ArticleVerdictOutput

    # Calendar has one published article with live_url.
    entries = [
        ContentCalendarEntry(
            id="tutorial-hell-progress",
            status=ArticleStatus.published,
            title="...",
            primary_keyword="tutorial hell",
            secondary_keywords=["stop watching tutorials"],
            article_type=ArticleType.standard,
            target_audience="...",
            angle="...",
            meta_description="...",
            published_at="2026-04-27",
            live_url="https://www.draftandarc.com/blog/tutorial-hell-progress",
        )
    ]

    gsc_rows = [
        {
            "page": "https://www.draftandarc.com/blog/tutorial-hell-progress",
            "query": "how to get rid of tutorial hell",
            "clicks": 8, "impressions": 142, "ctr": 0.0563, "position": 9.2,
        },
    ]

    ga4_rows = [
        {
            "page_path": "/blog/tutorial-hell-progress",
            "source_medium": "google / organic",
            "active_users": 24, "engaged_sessions": 18,
            "avg_session_duration": 102.5,
        }
    ]
    ga4_cta_by_path = {"/blog/tutorial-hell-progress": 2}

    dfs_ranked = [
        {"keyword": "tutorial hell python", "position": 28.0, "volume": 90,
         "url": "https://www.draftandarc.com/blog/tutorial-hell-progress"},
    ]

    mock_synthesis_output = MeasurementBriefOutput(
        actions=[],
        article_verdicts=[
            ArticleVerdictOutput(
                article_id="tutorial-hell-progress",
                verdict="On page 1 — keep the angle.",
            )
        ],
        coverage_note="All three sources reporting normally.",
    )

    with patch("agents.measurement_agent.load_calendar", AsyncMock(return_value=entries)), \
         patch("agents.measurement_agent.gsc_client") as mock_gsc, \
         patch("agents.measurement_agent.ga4_client") as mock_ga4, \
         patch("agents.measurement_agent.get_dfs_client") as mock_get_dfs, \
         patch("agents.measurement_agent.get_llm") as mock_get_llm, \
         patch("agents.measurement_agent.file_service.read_text", AsyncMock(return_value="## Product Facts\n- x")):

        mock_gsc.query_blog_performance = AsyncMock(return_value=gsc_rows)
        mock_ga4.query_blog_engagement = AsyncMock(return_value=(ga4_rows, ga4_cta_by_path))

        mock_dfs = MagicMock()
        mock_dfs.ranked_keywords_for_site = AsyncMock(return_value=dfs_ranked)
        mock_get_dfs.return_value = mock_dfs

        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_synthesis_output)
        mock_llm.with_structured_output.return_value = mock_chain
        mock_get_llm.return_value = mock_llm

        # measurement_synthesis_prompt is a ChatPromptTemplate; patch its __or__ so LCEL
        # doesn't try to coerce mock_llm into a RunnableLambda (same pattern as test_seo_agent).
        with patch.object(measurement_agent, "measurement_synthesis_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            final_report = await measurement_agent.run_measurement_agent(days=28)

    # Deterministic side intact.
    assert len(final_report.report.per_article) == 1
    article = final_report.report.per_article[0]
    assert article.article_id == "tutorial-hell-progress"
    assert "position" in article.metrics
    # LLM-side merged in.
    assert "page 1" in final_report.verdicts["tutorial-hell-progress"].lower()
    # Deterministic status notes prepended to LLM coverage_note.
    assert "All three sources" in final_report.coverage_note


async def test_run_measure_surfaces_skipped_articles_missing_live_url():
    """A published entry missing live_url MUST appear in coverage_note,
    not silently disappear from the brief (spec backfill note)."""
    from agents import measurement_agent
    from models.article import ContentCalendarEntry, ArticleStatus, ArticleType
    from output_schemas import MeasurementBriefOutput

    entries = [
        ContentCalendarEntry(
            id="legacy-article",
            status=ArticleStatus.published,
            title="...",
            primary_keyword="...",
            secondary_keywords=[],
            article_type=ArticleType.standard,
            target_audience="...",
            angle="...",
            meta_description="...",
            # NO published_at, NO live_url — legacy pre-spec entry.
        )
    ]

    mock_output = MeasurementBriefOutput(actions=[], article_verdicts=[], coverage_note="")

    with patch("agents.measurement_agent.load_calendar", AsyncMock(return_value=entries)), \
         patch("agents.measurement_agent.gsc_client") as mock_gsc, \
         patch("agents.measurement_agent.ga4_client") as mock_ga4, \
         patch("agents.measurement_agent.get_dfs_client") as mock_get_dfs, \
         patch("agents.measurement_agent.get_llm") as mock_get_llm, \
         patch("agents.measurement_agent.file_service.read_text", AsyncMock(return_value="facts")):

        mock_gsc.query_blog_performance = AsyncMock(return_value=[])
        mock_ga4.query_blog_engagement = AsyncMock(return_value=([], {}))

        mock_dfs = MagicMock()
        mock_dfs.ranked_keywords_for_site = AsyncMock(return_value=[])
        mock_get_dfs.return_value = mock_dfs

        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_chain
        mock_get_llm.return_value = mock_llm

        with patch.object(measurement_agent, "measurement_synthesis_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            final = await measurement_agent.run_measurement_agent(days=28)

    assert "legacy-article" in final.coverage_note
    assert "missing live_url" in final.coverage_note or "live_url/published_at" in final.coverage_note
    # Article must NOT silently appear in per_article — it should be skipped.
    assert final.report.per_article == []


async def test_run_measure_prepends_status_notes_before_llm_coverage():
    """When both deterministic notes AND an LLM coverage_note exist, the
    deterministic notes MUST come first so a failed data source can't be
    softened or hidden by LLM phrasing (spec Section 6)."""
    from agents import measurement_agent
    from output_schemas import MeasurementBriefOutput

    # GSC fetch fails; LLM still produces a coverage_note.
    mock_output = MeasurementBriefOutput(
        actions=[],
        article_verdicts=[],
        coverage_note="The remaining data sources look healthy this week.",
    )

    with patch("agents.measurement_agent.load_calendar", AsyncMock(return_value=[])), \
         patch("agents.measurement_agent.gsc_client") as mock_gsc, \
         patch("agents.measurement_agent.ga4_client") as mock_ga4, \
         patch("agents.measurement_agent.get_dfs_client") as mock_get_dfs, \
         patch("agents.measurement_agent.get_llm") as mock_get_llm, \
         patch("agents.measurement_agent.file_service.read_text", AsyncMock(return_value="facts")):

        # GSC raises — this becomes a status note.
        mock_gsc.query_blog_performance = AsyncMock(side_effect=RuntimeError("403 Forbidden"))
        mock_ga4.query_blog_engagement = AsyncMock(return_value=([], {}))

        mock_dfs = MagicMock()
        mock_dfs.ranked_keywords_for_site = AsyncMock(return_value=[])
        mock_get_dfs.return_value = mock_dfs

        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_chain
        mock_get_llm.return_value = mock_llm

        with patch.object(measurement_agent, "measurement_synthesis_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            final = await measurement_agent.run_measurement_agent(days=28)

    # The deterministic GSC failure note must appear, AND it must appear
    # BEFORE the LLM's coverage_note in the final string.
    assert "GSC fetch failed" in final.coverage_note
    assert "403 Forbidden" in final.coverage_note
    assert "remaining data sources look healthy" in final.coverage_note

    gsc_pos = final.coverage_note.index("GSC fetch failed")
    llm_pos = final.coverage_note.index("remaining data sources look healthy")
    assert gsc_pos < llm_pos, (
        f"Deterministic status note must precede LLM coverage prose; "
        f"got gsc_pos={gsc_pos}, llm_pos={llm_pos}"
    )
