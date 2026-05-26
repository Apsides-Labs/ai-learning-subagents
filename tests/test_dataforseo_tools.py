"""@tool wrappers in tools/dataforseo.py."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def test_dfs_serp_live_advanced_returns_formatted_summary():
    from services import dataforseo_client as client_mod
    from tools.dataforseo import dfs_serp_live_advanced

    client_mod._client = None
    payload = _load_fixture("dfs_serp_response.json")

    with patch.object(client_mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = client_mod.get_client()
        client._http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_resp.raise_for_status = MagicMock()
        client._http.post = AsyncMock(return_value=mock_resp)

        result = await dfs_serp_live_advanced.ainvoke({"query": "how to get rid of tutorial hell"})

    assert "reddit.com" in result
    assert "How do you escape tutorial hell?" in result  # PAA question, surfaced
    assert "rank 1" in result.lower() or "#1" in result


async def test_dfs_keyword_suggestions_returns_compact_list():
    from services import dataforseo_client as client_mod
    from tools.dataforseo import dfs_keyword_suggestions

    client_mod._client = None
    payload = _load_fixture("dfs_keyword_suggestions_response.json")

    with patch.object(client_mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = client_mod.get_client()
        client._http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_resp.raise_for_status = MagicMock()
        client._http.post = AsyncMock(return_value=mock_resp)

        result = await dfs_keyword_suggestions.ainvoke({"seed": "tutorial hell"})

    assert "tutorial hell programming" in result
    assert "480" in result   # search volume
    assert "22" in result    # difficulty


async def test_dfs_bulk_keyword_data_merges_volume_and_difficulty():
    from services import dataforseo_client as client_mod
    from tools.dataforseo import dfs_bulk_keyword_data

    client_mod._client = None
    vol_payload = _load_fixture("dfs_search_volume_response.json")
    diff_payload = _load_fixture("dfs_keyword_difficulty_response.json")

    with patch.object(client_mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = client_mod.get_client()
        client._http = MagicMock()

        # First POST call returns volume, second returns difficulty.
        responses = [vol_payload, diff_payload]

        async def fake_post(path, json):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=responses.pop(0))
            return resp

        client._http.post = AsyncMock(side_effect=fake_post)

        result = await dfs_bulk_keyword_data.ainvoke({
            "keywords": ["tutorial hell", "how to get rid of tutorial hell"]
        })

    assert "tutorial hell" in result
    assert "880" in result        # volume
    assert "28" in result         # difficulty
    assert "how to get rid of tutorial hell" in result
    assert "19" in result
    # Two API calls counted in cost tracker.
    assert client.tracker.total_calls == 2
