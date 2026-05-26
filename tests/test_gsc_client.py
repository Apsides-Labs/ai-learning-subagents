"""GSC client tests. Mocks googleapiclient.discovery.build."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def test_query_blog_performance_returns_typed_rows():
    from services import gsc_client

    response = _load_fixture("gsc_search_analytics_response.json")

    mock_service = MagicMock()
    mock_service.searchanalytics().query().execute.return_value = response

    with patch.object(gsc_client, "_build_service", return_value=mock_service), \
         patch.object(gsc_client, "settings") as mock_settings:
        mock_settings.gsc_site_url = "sc-domain:draftandarc.com"
        mock_settings.google_application_credentials = "/tmp/fake.json"

        rows = await gsc_client.query_blog_performance(
            start_date=date(2026, 4, 21),
            end_date=date(2026, 5, 19),
        )

    assert len(rows) == 3
    assert rows[0]["page"] == "https://www.draftandarc.com/blog/tutorial-hell-progress"
    assert rows[0]["query"] == "how to get rid of tutorial hell"
    assert rows[0]["clicks"] == 8
    assert rows[0]["impressions"] == 142
    assert rows[0]["position"] == 9.2


async def test_query_blog_performance_handles_empty_response():
    from services import gsc_client

    mock_service = MagicMock()
    mock_service.searchanalytics().query().execute.return_value = {}  # no 'rows'

    with patch.object(gsc_client, "_build_service", return_value=mock_service), \
         patch.object(gsc_client, "settings") as mock_settings:
        mock_settings.gsc_site_url = "sc-domain:draftandarc.com"
        mock_settings.google_application_credentials = "/tmp/fake.json"

        rows = await gsc_client.query_blog_performance(
            start_date=date(2026, 4, 21),
            end_date=date(2026, 5, 19),
        )

    assert rows == []
