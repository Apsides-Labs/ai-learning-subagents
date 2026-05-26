"""Tools package. Re-exports research-agent tools.

DataForSEO tools (the SEO agent's tool list) live in `tools.dataforseo`.
"""
from pathlib import Path
import httpx
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from config import settings


@tool
async def jina_reader(url: str) -> str:
    """Read the text content of any URL using Jina AI Reader. Use for competitor pages."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(f"https://r.jina.ai/{url}")
        response.raise_for_status()
        return response.text


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
