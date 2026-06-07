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
        items = payload["tasks"][0]["result"][0]["items"] or []
    except (KeyError, IndexError, TypeError):
        return f"No keyword suggestions for {seed!r}."

    if not items:
        return f"No keyword suggestions for {seed!r}."

    lines = [f"Keyword suggestions for {seed!r} (top {min(len(items), 20)}):"]
    for item in items[:20]:
        kw = item.get("keyword", "")
        vol = item.get("search_volume", "—")
        diff = item.get("keyword_difficulty", "—")
        lines.append(f"  - {kw} (volume {vol}, difficulty {diff})")
    return "\n".join(lines)


@tool
async def dfs_bulk_keyword_data(keywords: list[str]) -> str:
    """Get monthly search volume + keyword difficulty for a batch of keywords.

    Wraps two DFS endpoints (Google Ads Search Volume + Labs Bulk Keyword
    Difficulty) and merges results on the keyword string. Use once per
    candidate batch (post-filtering) to identify obviously bad bets.
    """
    if not keywords:
        return "No keywords provided."

    client = get_client()

    # Endpoint 1: search volume.
    vol_payload = await client.post(
        "/v3/keywords_data/google_ads/search_volume/live",
        json_body=[{
            "keywords": keywords,
            "location_code": 2840,
            "language_code": "en",
        }],
    )

    # Endpoint 2: keyword difficulty.
    diff_payload = await client.post(
        "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live",
        json_body=[{
            "keywords": keywords,
            "location_code": 2840,
            "language_code": "en",
        }],
    )

    # Build per-keyword dictionaries.
    volume_by_kw: dict[str, dict] = {}
    try:
        for row in vol_payload["tasks"][0]["result"]:
            volume_by_kw[row["keyword"]] = row
    except (KeyError, IndexError, TypeError):
        pass

    difficulty_by_kw: dict[str, int | None] = {}
    try:
        items = diff_payload["tasks"][0]["result"][0]["items"]
        for row in items:
            difficulty_by_kw[row["keyword"]] = row.get("keyword_difficulty")
    except (KeyError, IndexError, TypeError):
        pass

    lines = [f"Bulk data for {len(keywords)} keywords:"]
    for kw in keywords:
        vol_row = volume_by_kw.get(kw, {})
        vol = vol_row.get("search_volume", "—")
        cpc = vol_row.get("cpc", "—")
        comp = vol_row.get("competition", "—")
        diff = difficulty_by_kw.get(kw, "—")
        lines.append(
            f"  - {kw}: volume={vol}, difficulty={diff}, cpc={cpc}, competition={comp}"
        )
    return "\n".join(lines)
