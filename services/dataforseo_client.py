"""DataForSEO HTTP client + cost tracking.

Module-level singleton via get_client(). All @tool wrappers in
tools/dataforseo.py call into the same instance so the CostTracker
cap applies across one main.py invocation.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from config import settings


class DataForSEOBudgetExceeded(RuntimeError):
    """Raised when the per-run cost or call cap is exceeded."""


# Transient network failures worth retrying. The SERP live/advanced endpoint is
# slow and occasionally drops the connection or stalls past the read timeout; a
# single retry usually succeeds. Status errors (4xx/5xx) are NOT retried here —
# they are deterministic and surface immediately.
_RETRYABLE = (httpx.TimeoutException, httpx.TransportError)
# Server-side status codes worth retrying: rate limit + transient gateway errors.
# 4xx other than 429 are deterministic (bad request, auth) and surface immediately.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3          # total attempts = _MAX_RETRIES + 1
_RETRY_BACKOFF_S = 2.0    # linear backoff: 2s, 4s, 6s, ...


@dataclass
class CostTracker:
    max_cost: float
    max_calls: int
    total_cost: float = 0.0
    total_calls: int = 0
    _recent: deque = field(default_factory=lambda: deque(maxlen=5))

    def record(self, *, cost: float, endpoint: str) -> None:
        prospective_cost = self.total_cost + cost
        prospective_calls = self.total_calls + 1

        if prospective_cost > self.max_cost:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO cost cap of ${self.max_cost:.2f} would be exceeded "
                f"(current ${self.total_cost:.4f} + ${cost:.4f}); "
                f"recent endpoints: {list(self._recent)}"
            )
        if prospective_calls > self.max_calls:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO call cap of {self.max_calls} would be exceeded "
                f"(current {self.total_calls} + 1); "
                f"recent endpoints: {list(self._recent)}"
            )

        self.total_cost = prospective_cost
        self.total_calls = prospective_calls
        self._recent.append(endpoint)


class DataForSEOClient:
    """Thin HTTP wrapper. Auth via HTTP Basic. Cost tracked per call.

    Endpoints used by this project (in order of call frequency):
      - POST /v3/serp/google/organic/live/advanced   (~$0.002/query)
      - POST /v3/keywords_data/google_ads/search_volume/live   (~$0.05/1000 kw)
      - POST /v3/dataforseo_labs/google/bulk_keyword_difficulty/live   (~$0.01/1000 kw)
      - POST /v3/dataforseo_labs/google/keyword_suggestions/live   (~$0.01/task)
      - POST /v3/dataforseo_labs/google/ranked_keywords/live   (~$0.02/task)
      - GET  /v3/appendix/user_data   (free; used for --mode validate)

    Pricing is the spec's Section 4 estimate; verify against the dashboard
    during implementation Step 0 (see plan Task 0 in spec).
    """

    BASE_URL = "https://api.dataforseo.com"

    def __init__(self) -> None:
        if not settings.dataforseo_login or not settings.dataforseo_password:
            raise RuntimeError(
                "DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD must be set in .env"
            )
        # Generous read timeout: the SERP live/advanced endpoint computes on
        # request and can take well over 30s. Connect stays short so a dead
        # host fails fast.
        self._http = httpx.AsyncClient(
            base_url=self.BASE_URL,
            auth=(settings.dataforseo_login, settings.dataforseo_password),
            timeout=httpx.Timeout(90.0, connect=10.0),
        )
        self.tracker = CostTracker(
            max_cost=settings.dataforseo_max_cost_per_run,
            max_calls=settings.dataforseo_max_calls_per_run,
        )

    async def _request(self, method: str, path: str, *, json_body: Any = None) -> dict:
        """Send one request, retrying transient network failures.

        Cost is recorded only after a successful response is parsed, so failed
        attempts never touch the budget tracker. Note: a retry after a read
        timeout may re-run a request the server already executed, so a slow
        endpoint can be charged more than once — the per-run cost cap bounds the
        worst case.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                if method == "POST":
                    response = await self._http.post(path, json=json_body)
                else:
                    response = await self._http.get(path)
                response.raise_for_status()
                payload = response.json()
                cost = float(payload.get("cost", 0.0))
                self.tracker.record(cost=cost, endpoint=path)
                return payload
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRYABLE_STATUS:
                    raise  # deterministic (400/401/403/404) — don't retry
                last_exc = exc
            except _RETRYABLE as exc:
                last_exc = exc

            if attempt < _MAX_RETRIES:
                print(
                    f"  DataForSEO {method} {path} failed ({type(last_exc).__name__}); "
                    f"retry {attempt + 1}/{_MAX_RETRIES}..."
                )
                await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    async def post(self, path: str, *, json_body: Any) -> dict:
        return await self._request("POST", path, json_body=json_body)

    async def get(self, path: str) -> dict:
        return await self._request("GET", path)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def validate(self) -> tuple[bool, str]:
        """Cheap auth check via /v3/appendix/user_data (free endpoint).

        Returns (ok, message). On success the message includes account balance.
        On failure the message describes the auth or HTTP problem.
        """
        try:
            payload = await self.get("/v3/appendix/user_data")
        except httpx.HTTPStatusError as exc:
            return False, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Request failed: {exc}"

        try:
            info = payload["tasks"][0]["result"][0]
            balance = info.get("balance", "unknown")
            login = info.get("login", "unknown")
            return True, f"DataForSEO ok. Account: {login}. Balance: ${balance}"
        except (KeyError, IndexError, TypeError):
            return False, f"Unexpected response shape: {payload}"

    async def bulk_keyword_metrics(self, keywords: list[str]) -> dict[str, dict]:
        """Return {keyword: {"search_volume": int|None, "keyword_difficulty": int|None}}.

        Structured sibling of tools.dataforseo.dfs_bulk_keyword_data (which
        returns a string for the agent). Used by propose mode to attach SEO
        numbers to candidates. Merges the Google Ads search-volume and Labs
        bulk-difficulty endpoints on the keyword string.
        """
        if not keywords:
            return {}

        vol_payload = await self.post(
            "/v3/keywords_data/google_ads/search_volume/live",
            json_body=[{
                "keywords": keywords,
                "location_code": 2840,
                "language_code": "en",
            }],
        )
        diff_payload = await self.post(
            "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live",
            json_body=[{
                "keywords": keywords,
                "location_code": 2840,
                "language_code": "en",
            }],
        )

        volume_by_kw: dict[str, int | None] = {}
        try:
            for row in vol_payload["tasks"][0]["result"]:
                volume_by_kw[row["keyword"]] = row.get("search_volume")
        except (KeyError, IndexError, TypeError):
            pass

        difficulty_by_kw: dict[str, int | None] = {}
        try:
            for row in diff_payload["tasks"][0]["result"][0]["items"]:
                difficulty_by_kw[row["keyword"]] = row.get("keyword_difficulty")
        except (KeyError, IndexError, TypeError):
            pass

        return {
            kw: {
                "search_volume": volume_by_kw.get(kw),
                "keyword_difficulty": difficulty_by_kw.get(kw),
            }
            for kw in keywords
        }

    async def keyword_ideas(self, seed: str, *, limit: int = 30) -> list[dict]:
        """Real long-tail variants for `seed`, each with volume + difficulty.

        Structured sibling of tools.dataforseo.dfs_keyword_suggestions. Used by
        propose mode to replace the LLM's guessed keyword with a phrase people
        actually search. Returns [{keyword, search_volume, keyword_difficulty}].
        """
        payload = await self.post(
            "/v3/dataforseo_labs/google/keyword_suggestions/live",
            json_body=[{
                "keyword": seed,
                "location_code": 2840,
                "language_code": "en",
                "limit": limit,
            }],
        )
        try:
            items = payload["tasks"][0]["result"][0]["items"] or []
        except (KeyError, IndexError, TypeError):
            return []

        ideas: list[dict] = []
        for item in items:
            # Volume/difficulty are flat on suggestion items; fall back to the
            # nested keyword_info/keyword_properties shape if a variant differs.
            info = item.get("keyword_info") or {}
            props = item.get("keyword_properties") or {}
            ideas.append({
                "keyword": item.get("keyword", ""),
                "search_volume": item.get("search_volume", info.get("search_volume")),
                "keyword_difficulty": item.get(
                    "keyword_difficulty", props.get("keyword_difficulty")
                ),
            })
        return [i for i in ideas if i["keyword"]]

    async def serp_snapshot(self, keyword: str) -> dict:
        """Top organic domains + People-Also-Ask for `keyword`.

        Returns {"organic": [{"rank", "domain", "title"}], "paa": [questions]}.
        Used by propose mode to assess SERP reachability per candidate.
        """
        payload = await self.post(
            "/v3/serp/google/organic/live/advanced",
            json_body=[{
                "keyword": keyword,
                "location_code": 2840,
                "language_code": "en",
                "depth": 10,
            }],
        )
        try:
            items = payload["tasks"][0]["result"][0].get("items", []) or []
        except (KeyError, IndexError, TypeError):
            return {"organic": [], "paa": []}

        organic: list[dict] = []
        paa: list[str] = []
        for item in items:
            kind = item.get("type")
            if kind == "organic":
                organic.append({
                    "rank": item.get("rank_absolute"),
                    "domain": item.get("domain", ""),
                    "title": item.get("title", ""),
                })
            elif kind == "people_also_ask_element":
                for q in item.get("items", []):
                    title = (q.get("title") or "").strip()
                    if title:
                        paa.append(title)
        return {"organic": organic, "paa": paa}

    async def ranked_keywords_for_site(
        self,
        target: str,
        *,
        url_substring: str = "",
        limit: int = 1000,
    ) -> list[dict]:
        """All keywords the target domain currently ranks for.

        Returns a list of dicts with keys: keyword, position, search_volume, url.
        If `url_substring` is given, filters to ranked URLs containing it
        (we use "/blog/" because the DFS endpoint takes a domain target, not
        a path prefix — see spec Section 6).
        """
        payload = await self.post(
            "/v3/dataforseo_labs/google/ranked_keywords/live",
            json_body=[{
                "target": target,
                "location_code": 2840,
                "language_code": "en",
                "limit": limit,
            }],
        )

        rows: list[dict] = []
        try:
            items = payload["tasks"][0]["result"][0]["items"] or []
        except (KeyError, IndexError, TypeError):
            return rows

        for item in items:
            kd = item.get("keyword_data") or {}
            rse = item.get("ranked_serp_element") or {}
            url = rse.get("url", "")
            if url_substring and url_substring not in url:
                continue
            rows.append({
                "keyword": kd.get("keyword", ""),
                "position": rse.get("rank_absolute", 0),
                "search_volume": kd.get("search_volume", 0),
                "url": url,
            })
        return rows


_client: Optional[DataForSEOClient] = None


def get_client() -> DataForSEOClient:
    """Return the process-scoped singleton client.

    The CostTracker on the instance is shared across all @tool calls
    in one main.py invocation, so caps apply at the right granularity.
    """
    global _client
    if _client is None:
        _client = DataForSEOClient()
    return _client
