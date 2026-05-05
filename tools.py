from pathlib import Path
import httpx
import requests.exceptions
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from pytrends import exceptions as pytrends_exceptions
from pytrends.request import TrendReq
from config import settings


@tool
async def jina_reader(url: str) -> str:
    """Read the text content of any URL using Jina AI Reader. Use for competitor pages."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(f"https://r.jina.ai/{url}")
        response.raise_for_status()
        return response.text


@tool
def google_trends(keyword: str) -> str:
    """Check Google Trends interest for a keyword. Returns: rising, stable, falling, or no_data."""
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], timeframe="today 12-m")
        df = pytrends.interest_over_time()
    except (requests.exceptions.RequestException, pytrends_exceptions.ResponseCodeError) as e:
        return f"no_data (trend lookup failed: {type(e).__name__})"
    if df.empty or keyword not in df.columns:
        return "no_data"
    values = df[keyword].tolist()
    mid = len(values) // 2
    first_half = sum(values[:mid]) or 1
    second_half = sum(values[mid:]) or 0
    if second_half > first_half * 1.1:
        return "rising"
    if second_half < first_half * 0.9:
        return "falling"
    return "stable"


@tool
def people_also_ask(query: str) -> str:
    """Get People Also Ask questions from Google for a query. Best source of long-tail keywords."""
    from serpapi import GoogleSearch
    search = GoogleSearch({"q": query, "api_key": settings.serpapi_api_key})
    results = search.get_dict()
    questions = [q.get("question", "") for q in results.get("related_questions", [])[:10]]
    if not questions:
        return "No People Also Ask results found."
    return "\n".join(questions)


@tool
def list_codebase_files(directory: str = "") -> str:
    """List Python files in the Draft and Arc codebase. Use to discover what to read."""
    base = Path(settings.codebase_path) / directory
    if not base.exists():
        return f"Directory not found: {directory}"
    files = [
        str(f.relative_to(Path(settings.codebase_path)))
        for f in base.rglob("*.py")
        if "__pycache__" not in str(f)
    ]
    return "\n".join(sorted(files)[:60])


@tool
def read_codebase_file(relative_path: str) -> str:
    """Read a specific file from the Draft and Arc codebase. Use for extracting product facts."""
    path = Path(settings.codebase_path) / relative_path
    if not path.exists():
        return f"File not found: {relative_path}"
    return path.read_text(encoding="utf-8")


tavily_search_tool = TavilySearch(max_results=5)
