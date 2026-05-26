"""GA4 client tests. Mocks BetaAnalyticsDataAsyncClient.run_report."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _build_mock_response(fixture_name: str):
    """Build a mock RunReportResponse-shaped object from a fixture."""
    payload = _load_fixture(fixture_name)
    resp = MagicMock()
    rows = []
    for raw_row in payload["rows"]:
        row = MagicMock()
        row.dimension_values = [MagicMock(value=dv["value"]) for dv in raw_row["dimensionValues"]]
        row.metric_values = [MagicMock(value=mv["value"]) for mv in raw_row["metricValues"]]
        rows.append(row)
    resp.rows = rows
    return resp


async def test_query_blog_engagement_returns_rows_and_cta_separately():
    """GA4 client returns a (rows, cta_clicks_by_path) tuple. The separation
    means downstream code doesn't have to do a fragile divide-by-row-count
    trick to dedupe per-path CTA counts across multiple source/medium splits."""
    from services import ga4_client

    eng = _build_mock_response("ga4_engagement_response.json")
    conv = _build_mock_response("ga4_conversion_response.json")

    mock_async_client = MagicMock()
    mock_async_client.run_report = AsyncMock(side_effect=[eng, conv])

    with patch.object(ga4_client, "_build_async_client", return_value=mock_async_client), \
         patch.object(ga4_client, "settings") as mock_settings:
        mock_settings.ga4_property_id = "123456789"
        mock_settings.google_application_credentials = "/tmp/fake.json"

        rows, cta_by_path = await ga4_client.query_blog_engagement(
            start_date=date(2026, 4, 21),
            end_date=date(2026, 5, 19),
        )

    # Engagement rows for tutorial-hell-progress (2 source/medium splits).
    by_key = {(r["page_path"], r["source_medium"]): r for r in rows}

    organic = by_key[("/blog/tutorial-hell-progress", "google / organic")]
    assert organic["active_users"] == 24
    assert organic["engaged_sessions"] == 18
    assert organic["avg_session_duration"] == 102.5

    twitter = by_key[("/blog/tutorial-hell-progress", "twitter / referral")]
    assert twitter["active_users"] == 3

    anki = by_key[("/blog/anki-review-queue-burnout", "(direct) / (none)")]
    assert anki["active_users"] == 1

    # CTA attribution is per-path, not per-split. Returned as a dict.
    assert cta_by_path == {"/blog/tutorial-hell-progress": 2}
