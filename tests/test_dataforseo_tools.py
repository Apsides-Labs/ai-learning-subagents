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
