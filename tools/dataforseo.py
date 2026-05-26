"""DataForSEO @tool wrappers for the SEO agent.

The DFS API returns sprawling JSON; each wrapper normalizes one call into
a compact string the LLM agent can reason over. Compact > complete here —
the SEO agent's job is selection, not analysis of raw JSON.

Tools added across Tasks 8-10:
  - dfs_serp_live_advanced       (this task)
  - dfs_keyword_suggestions      (Task 9)
  - dfs_bulk_keyword_data        (Task 10)

The DFS Labs ranked-keywords-for-site call lives in
services/dataforseo_client.py (not wrapped as @tool) because it's only
called from measurement_agent — see Task 30.
"""

from langchain_core.tools import tool

from services.dataforseo_client import get_client


@tool
async def dfs_serp_live_advanced(query: str) -> str:
    """Fetch Google SERP for one query. Returns top organic results + People Also Ask.

    Use for SERP inspection: who's ranking, how strong/weak, what content type.
    One call per shortlisted keyword candidate.
    """
    client = get_client()
    payload = await client.post(
        "/v3/serp/google/organic/live/advanced",
        json_body=[{
            "keyword": query,
            "location_code": 2840,   # United States
            "language_code": "en",
            "depth": 10,
        }],
    )

    try:
        result = payload["tasks"][0]["result"][0]
    except (KeyError, IndexError):
        return f"No SERP result for {query!r}."

    lines = [f"SERP for {query!r}:"]
    paa_questions: list[str] = []

    for item in result.get("items", []):
        kind = item.get("type")
        if kind == "organic":
            rank = item.get("rank_absolute", "?")
            domain = item.get("domain", "")
            title = item.get("title", "")
            lines.append(f"  #{rank} {domain} — {title}")
        elif kind == "people_also_ask_element":
            for paa in item.get("items", []):
                q = paa.get("title", "").strip()
                if q:
                    paa_questions.append(q)

    if paa_questions:
        lines.append("")
        lines.append("People Also Ask:")
        for q in paa_questions[:5]:
            lines.append(f"  - {q}")

    return "\n".join(lines)


@tool
async def dfs_keyword_suggestions(seed: str) -> str:
    """Return long-tail keyword variants for a seed. Includes volume + difficulty.

    Use once per content opportunity during candidate generation to surface
    PAA-style phrasings the seed itself doesn't capture.
    """
    client = get_client()
    payload = await client.post(
        "/v3/dataforseo_labs/google/keyword_suggestions/live",
        json_body=[{
            "keyword": seed,
            "location_code": 2840,
            "language_code": "en",
            "limit": 20,
        }],
    )

    try:
        items = payload["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError):
        return f"No keyword suggestions for {seed!r}."

    lines = [f"Keyword suggestions for {seed!r} (top {min(len(items), 20)}):"]
    for item in items[:20]:
        kw = item.get("keyword", "")
        vol = item.get("search_volume", "—")
        diff = item.get("keyword_difficulty", "—")
        lines.append(f"  - {kw} (volume {vol}, difficulty {diff})")
    return "\n".join(lines)
