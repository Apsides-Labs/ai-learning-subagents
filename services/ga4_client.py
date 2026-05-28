"""GA4 client.

Uses google-analytics-data's async client (BetaAnalyticsDataAsyncClient).
Runs two reports — engagement and conversion — and merges client-side on
pagePath. See spec Section 5 for why a single report cannot do this.
"""

from datetime import date
from typing import Any

from google.analytics.data_v1beta import BetaAnalyticsDataAsyncClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

from config import settings


SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _build_async_client() -> BetaAnalyticsDataAsyncClient:
    if not settings.google_application_credentials:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS must be set in .env")
    if not settings.ga4_property_id:
        raise RuntimeError("GA4_PROPERTY_ID must be set in .env")

    creds = service_account.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=SCOPES,
    )
    return BetaAnalyticsDataAsyncClient(credentials=creds)


def _blog_path_filter() -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name="pagePath",
            string_filter=Filter.StringFilter(
                value="/blog/",
                match_type=Filter.StringFilter.MatchType.CONTAINS,
            ),
        )
    )


async def query_blog_engagement(
    start_date: date, end_date: date
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Per-(pagePath, sourceMedium) engagement + per-pagePath CTA conversion.

    Returns a tuple:
      (engagement_rows, cta_clicks_by_path)

      engagement_rows: list of dicts with keys
        page_path, source_medium, active_users, engaged_sessions, avg_session_duration

      cta_clicks_by_path: dict mapping page_path → total cta_click count
        (the event name fired by the draftnarc Astro blog's Layout.astro;
        see services/ga4_client.py for the filter and docs/playbooks/seo/
        04-measurement-cheatsheet.md for the broader CTA story)

    Returning these separately (rather than denormalizing CTA into every
    engagement row) means downstream code doesn't have to dedupe a CTA
    count that's been duplicated across multiple source/medium splits.
    """
    client = _build_async_client()
    property_path = f"properties/{settings.ga4_property_id}"
    date_range = DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())

    # Report A: engagement, broken by source/medium.
    eng_request = RunReportRequest(
        property=property_path,
        date_ranges=[date_range],
        dimensions=[Dimension(name="pagePath"), Dimension(name="sessionSourceMedium")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="engagedSessions"),
            Metric(name="averageSessionDuration"),
        ],
        dimension_filter=_blog_path_filter(),
        limit=10000,
    )

    # Report B: conversion, filtered to the one event we care about.
    conv_request = RunReportRequest(
        property=property_path,
        date_ranges=[date_range],
        dimensions=[Dimension(name="pagePath"), Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            and_group=FilterExpressionList(expressions=[
                _blog_path_filter(),
                FilterExpression(filter=Filter(
                    field_name="eventName",
                    string_filter=Filter.StringFilter(
                        value="cta_click",
                        match_type=Filter.StringFilter.MatchType.EXACT,
                    ),
                )),
            ])
        ),
        limit=10000,
    )

    eng_resp = await client.run_report(eng_request)
    conv_resp = await client.run_report(conv_request)

    # Aggregate conversion rows by pagePath.
    cta_by_path: dict[str, int] = {}
    for row in conv_resp.rows or []:
        page_path = row.dimension_values[0].value
        count = int(row.metric_values[0].value or 0)
        cta_by_path[page_path] = cta_by_path.get(page_path, 0) + count

    # Build engagement rows (no CTA field — that's returned separately).
    rows: list[dict[str, Any]] = []
    for row in eng_resp.rows or []:
        rows.append({
            "page_path": row.dimension_values[0].value,
            "source_medium": row.dimension_values[1].value,
            "active_users": int(row.metric_values[0].value or 0),
            "engaged_sessions": int(row.metric_values[1].value or 0),
            "avg_session_duration": float(row.metric_values[2].value or 0.0),
        })
    return rows, cta_by_path


async def validate() -> tuple[bool, str]:
    """Cheap check: one-row report today→today.

    Confirms the property ID + permission with a single Data API call.
    Avoids pulling in google-analytics-admin just for validation.
    """
    try:
        client = _build_async_client()
    except Exception as exc:  # noqa: BLE001
        return False, f"GA4 client build failed: {exc}"

    today = date.today().isoformat()
    request = RunReportRequest(
        property=f"properties/{settings.ga4_property_id}",
        date_ranges=[DateRange(start_date=today, end_date=today)],
        metrics=[Metric(name="activeUsers")],
        limit=1,
    )
    try:
        await client.run_report(request)
        return True, f"GA4 ok. Property: {settings.ga4_property_id}"
    except Exception as exc:  # noqa: BLE001
        return False, f"GA4 run_report failed: {exc}"
