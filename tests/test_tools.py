import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_jina_reader_returns_text():
    from tools import jina_reader
    mock_response = MagicMock()
    mock_response.text = "# Competitor Homepage\n\nWe offer X and Y."
    mock_response.raise_for_status = MagicMock()

    with patch("tools.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await jina_reader.ainvoke({"url": "https://example.com"})
        assert "Competitor Homepage" in result


def test_google_trends_rising():
    from tools import google_trends
    import pandas as pd
    mock_df = pd.DataFrame({"test keyword": [10, 10, 20, 20, 30, 30]})

    with patch("tools.TrendReq") as mock_trend_cls:
        mock_trend = MagicMock()
        mock_trend_cls.return_value = mock_trend
        mock_trend.interest_over_time.return_value = mock_df

        result = google_trends.invoke({"keyword": "test keyword"})
        assert result == "rising"


def test_google_trends_no_data():
    from tools import google_trends
    import pandas as pd

    with patch("tools.TrendReq") as mock_trend_cls:
        mock_trend = MagicMock()
        mock_trend_cls.return_value = mock_trend
        mock_trend.interest_over_time.return_value = pd.DataFrame()

        result = google_trends.invoke({"keyword": "obscure keyword"})
        assert result == "no_data"


def test_list_codebase_files(tmp_path):
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
    os.environ.setdefault("SERPAPI_API_KEY", "serp-test")

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "models.py").write_text("# models")
    (tmp_path / "app" / "__pycache__").mkdir()

    from tools import list_codebase_files
    with patch("tools.settings") as mock_settings:
        mock_settings.codebase_path = str(tmp_path)
        result = list_codebase_files.invoke({"directory": "app"})
        assert "models.py" in result
        assert "__pycache__" not in result


def test_read_codebase_file(tmp_path):
    (tmp_path / "test_file.py").write_text("x = 1")
    from tools import read_codebase_file
    with patch("tools.settings") as mock_settings:
        mock_settings.codebase_path = str(tmp_path)
        result = read_codebase_file.invoke({"relative_path": "test_file.py"})
        assert "x = 1" in result


def test_read_codebase_file_not_found(tmp_path):
    from tools import read_codebase_file
    with patch("tools.settings") as mock_settings:
        mock_settings.codebase_path = str(tmp_path)
        result = read_codebase_file.invoke({"relative_path": "missing.py"})
        assert "not found" in result.lower()
