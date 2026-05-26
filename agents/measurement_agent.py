"""Measurement agent: GSC + GA4 + DFS Labs → MeasurementReport → LLM synthesis → FinalMeasurementReport.

Numbers are deterministic; only the prose interpretation goes through an LLM.
"""

import asyncio
from datetime import date, timedelta
from urllib.parse import urlparse

from langchain_core.prompts import ChatPromptTemplate

from models.article import ArticleStatus, ContentCalendarEntry
from models.measurement import (
    DataSourceStatus,
    FinalMeasurementReport,
    GapOpportunity,
    MeasurementReport,
    MetricScore,
    QueryRow,
    ScoredArticlePerformance,
    normalize_url,
    report_to_synthesis_input,
)
from output_schemas import MeasurementBriefOutput
from prompts.loader import load_prompt
from services import file_service, ga4_client, gsc_client
from services.calendar_service import load_calendar
from services.dataforseo_client import get_client as get_dfs_client
from services.llm import get_llm
from services.scoring import (
    Label,
    expected_ctr_for_position,
    score_cta_rate,
    score_ctr,
    score_engagement_time,
    score_impressions,
    score_position,
)


GSC_LAG_DAYS = 3   # See spec Section 5: GSC 'final' data lags ~2-3 days.


measurement_synthesis_prompt = load_prompt("chains/measurement_synthesis.md")


def _worst_label(labels: list[Label]) -> Label:
    """Roll up per-metric labels into an overall label. Worst wins;
    INSUFFICIENT_DATA is skipped unless it's the only label."""
    if not labels:
        return Label.insufficient_data
    rank = {Label.poor: 3, Label.borderline: 2, Label.good: 1, Label.insufficient_data: 0}
    non_insufficient = [l for l in labels if l != Label.insufficient_data]
    if not non_insufficient:
        return Label.insufficient_data
    return max(non_insufficient, key=lambda l: rank[l])


def _format_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def _days_between(start: str, end_iso: date) -> int:
    return (end_iso - date.fromisoformat(start)).days


async def _safe_gsc(start, end):
    try:
        return await gsc_client.query_blog_performance(start, end), None
    except Exception as exc:  # noqa: BLE001
        return [], f"GSC fetch failed: {exc}"


async def _safe_ga4(start, end):
    """Returns ((rows, cta_by_path), error_message_or_none)."""
    try:
        rows, cta_by_path = await ga4_client.query_blog_engagement(start, end)
        return (rows, cta_by_path), None
    except Exception as exc:  # noqa: BLE001
        return ([], {}), f"GA4 fetch failed: {exc}"


async def _safe_dfs_ranked():
    try:
        client = get_dfs_client()
        rows = await client.ranked_keywords_for_site("draftandarc.com", url_substring="/blog/")
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], f"DataForSEO ranked-keywords fetch failed: {exc}"


def _aggregate_per_article(
    entries: list[ContentCalendarEntry],
    gsc_rows: list[dict],
    ga4_rows: list[dict],
    ga4_cta_by_path: dict[str, int],
    end_iso: date,
) -> tuple[list[ScoredArticlePerformance], list[str]]:
    """Join GSC + GA4 rows to calendar entries on exact normalized live_url.

    Returns (per_article, coverage_skipped_ids). Caller is expected to surface
    any skipped ids in DataSourceStatus.notes so they don't silently disappear
    from the brief.

    URL matching is intentionally asymmetric:
      - GSC returns FULL URLs in the 'page' field (host + path) → join on
        normalize_url(r["page"]) == normalize_url(entry.live_url).
      - GA4 returns only the path in 'page_path' → join on rstrip("/") of
        the path. Do NOT try to "unify" these — they're different upstream
        contracts.
    """
    out: list[ScoredArticlePerformance] = []
    coverage_skipped: list[str] = []

    for entry in entries:
        if entry.status != ArticleStatus.published:
            continue
        if not entry.live_url or not entry.published_at:
            coverage_skipped.append(entry.id)
            continue

        target_url = normalize_url(entry.live_url)
        # GSC join on full URL.
        gsc_for_article = [r for r in gsc_rows if normalize_url(r["page"]) == target_url]
        # GA4 join on pagePath only (different upstream contract — see docstring).
        target_path = urlparse(target_url).path
        ga4_for_article = [r for r in ga4_rows if r["page_path"].rstrip("/") == target_path]

        days_since = _days_between(entry.published_at, end_iso)

        impressions = sum(r["impressions"] for r in gsc_for_article)
        clicks = sum(r["clicks"] for r in gsc_for_article)
        avg_position = (
            sum(r["position"] * r["impressions"] for r in gsc_for_article) / impressions
            if impressions else 0.0
        )
        ctr = clicks / impressions if impressions else 0.0

        users = sum(r["active_users"] for r in ga4_for_article)
        avg_engagement = (
            sum(r["avg_session_duration"] * r["active_users"] for r in ga4_for_article) / users
            if users else 0.0
        )
        # CTA is attributed per-path; look up in the separate dict.
        cta_clicks = ga4_cta_by_path.get(target_path, 0)

        metrics = {
            "position": MetricScore(
                value=avg_position,
                display=f"pos {avg_position:.1f}",
                label=score_position(avg_position) if impressions else Label.insufficient_data,
                reason="page 1 sweet spot is 1-3" if avg_position < 3.5 else
                       ("on page 1" if avg_position < 10.5 else "page 2"),
            ),
            "ctr": MetricScore(
                value=ctr,
                display=f"{ctr * 100:.1f}%",
                label=score_ctr(ctr, avg_position) if impressions else Label.insufficient_data,
                reason=(
                    f"vs ~{expected_ctr_for_position(avg_position):.1%} expected at this position"
                    if impressions else "no impressions yet"
                ),
            ),
            "impressions": MetricScore(
                value=impressions,
                display=f"{impressions}",
                label=score_impressions(impressions, days_since),
                reason=("not yet 14 days post-publish" if days_since < 14 else
                        "100+ in 28d is healthy"),
            ),
            "engagement": MetricScore(
                value=avg_engagement,
                display=_format_duration(avg_engagement) if users else "no data",
                label=score_engagement_time(avg_engagement) if users else Label.insufficient_data,
                reason="2:00+ = actually read",
            ),
            "cta_rate": MetricScore(
                value=cta_clicks / users if users else 0.0,
                display=f"{cta_clicks}/{users}" if users else "no users",
                label=score_cta_rate(cta_clicks, users),
                reason="industry baseline 1-3%",
            ),
        }

        overall = _worst_label([m.label for m in metrics.values()])

        # Top queries: pick top 5 by impressions.
        top_queries = [
            QueryRow(
                query=r["query"], impressions=r["impressions"], clicks=r["clicks"],
                ctr=r["ctr"], position=r["position"],
            )
            for r in sorted(gsc_for_article, key=lambda x: x["impressions"], reverse=True)[:5]
        ]

        out.append(ScoredArticlePerformance(
            article_id=entry.id,
            url=entry.live_url,
            published_at=entry.published_at,
            days_since_publish=days_since,
            overall_label=overall,
            metrics=metrics,
            top_queries=top_queries,
        ))

    return out, coverage_skipped


def _gap_opportunities(
    entries: list[ContentCalendarEntry],
    dfs_ranked: list[dict],
) -> list[GapOpportunity]:
    """Keywords we rank for that we didn't target.

    Targeted set = primary + secondary across all calendar entries.
    Lowercased on both sides for the diff.
    """
    targeted: set[str] = set()
    for e in entries:
        targeted.add(e.primary_keyword.lower().strip())
        for kw in e.secondary_keywords:
            targeted.add(kw.lower().strip())

    out: list[GapOpportunity] = []
    for row in dfs_ranked:
        kw = (row.get("keyword") or "").lower().strip()
        if not kw or kw in targeted:
            continue
        out.append(GapOpportunity(
            keyword=row["keyword"],
            position=float(row.get("position", 0)),
            volume=int(row.get("volume", 0)),
            url=row.get("url", ""),
        ))
    # Sort by potential: low position + high volume first.
    out.sort(key=lambda g: (g.position, -g.volume))
    return out


async def run_measurement_agent(days: int = 28) -> FinalMeasurementReport:
    """Pull GSC + GA4 + DFS Labs data, score per-article metrics, synthesize via LLM."""
    end = date.today() - timedelta(days=GSC_LAG_DAYS)
    start = end - timedelta(days=days)

    entries = await load_calendar()

    # Parallel fetch. GA4 result is a (rows, cta_by_path) tuple.
    (gsc_rows, gsc_err), (ga4_result, ga4_err), (dfs_rows, dfs_err) = await asyncio.gather(
        _safe_gsc(start, end),
        _safe_ga4(start, end),
        _safe_dfs_ranked(),
    )
    ga4_rows, ga4_cta_by_path = ga4_result

    notes: list[str] = []
    if gsc_err: notes.append(gsc_err)
    if ga4_err: notes.append(ga4_err)
    if dfs_err: notes.append(dfs_err)

    per_article, skipped_ids = _aggregate_per_article(
        entries, gsc_rows, ga4_rows, ga4_cta_by_path, end
    )
    if skipped_ids:
        notes.append(
            f"{len(skipped_ids)} published article(s) missing live_url/published_at "
            f"and skipped: {', '.join(skipped_ids)}. "
            f"Run --mark-published <id> --url <live_url> to include."
        )

    status = DataSourceStatus(
        gsc_ok=gsc_err is None,
        ga4_ok=ga4_err is None,
        dfs_ok=dfs_err is None,
        notes=notes,
    )

    gap_opps = _gap_opportunities(entries, dfs_rows)

    headline = {
        "articles": len(per_article),
        "impressions": sum(r["impressions"] for r in gsc_rows),
        "clicks": sum(r["clicks"] for r in gsc_rows),
        "ctr": (sum(r["clicks"] for r in gsc_rows) / max(1, sum(r["impressions"] for r in gsc_rows))),
        "avg_position": (
            sum(r["position"] * r["impressions"] for r in gsc_rows)
            / max(1, sum(r["impressions"] for r in gsc_rows))
        ),
    }

    report = MeasurementReport(
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        headline=headline,
        per_article=per_article,
        gap_opportunities=gap_opps,
        data_source_status=status,
    )

    # LLM synthesis.
    product_facts = ""
    try:
        product_facts = await file_service.read_text(file_service.PRODUCT_FACTS_PATH)
    except Exception:
        pass

    chain = measurement_synthesis_prompt | get_llm().with_structured_output(
        MeasurementBriefOutput, method="function_calling"
    )
    synthesis_input = report_to_synthesis_input(report)
    output: MeasurementBriefOutput = await chain.ainvoke({
        "raw_data": synthesis_input,
        "product_facts": product_facts,
    })

    # Belt-and-suspenders: enforce article_id validity.
    valid_ids = {a.article_id for a in per_article}
    verdicts = {v.article_id: v.verdict for v in output.article_verdicts if v.article_id in valid_ids}

    # Spec Section 6: deterministic data_source_status.notes must be prepended
    # to the final coverage_note so a failed source / skipped article can't be
    # softened or omitted by the LLM.
    coverage_parts: list[str] = []
    if status.notes:
        coverage_parts.append("Data-source / coverage notes (deterministic):")
        for note in status.notes:
            coverage_parts.append(f"  - {note}")
    if output.coverage_note:
        coverage_parts.append(output.coverage_note)
    final_coverage_note = "\n".join(coverage_parts)

    return FinalMeasurementReport(
        report=report,
        actions=list(output.actions),
        verdicts=verdicts,
        coverage_note=final_coverage_note,
    )
