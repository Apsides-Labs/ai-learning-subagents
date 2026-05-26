"""DataForSEO HTTP client + cost tracking.

Module-level singleton via get_client(). All @tool wrappers in
tools/dataforseo.py call into the same instance so the CostTracker
cap applies across one main.py invocation.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from config import settings


class DataForSEOBudgetExceeded(RuntimeError):
    """Raised when the per-run cost or call cap is exceeded."""


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
        self._http = httpx.AsyncClient(
            base_url=self.BASE_URL,
            auth=(settings.dataforseo_login, settings.dataforseo_password),
            timeout=30.0,
        )
        self.tracker = CostTracker(
            max_cost=settings.dataforseo_max_cost_per_run,
            max_calls=settings.dataforseo_max_calls_per_run,
        )

    async def post(self, path: str, *, json_body: Any) -> dict:
        response = await self._http.post(path, json=json_body)
        response.raise_for_status()
        payload = response.json()
        cost = float(payload.get("cost", 0.0))
        self.tracker.record(cost=cost, endpoint=path)
        return payload

    async def get(self, path: str) -> dict:
        response = await self._http.get(path)
        response.raise_for_status()
        payload = response.json()
        cost = float(payload.get("cost", 0.0))
        self.tracker.record(cost=cost, endpoint=path)
        return payload

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
            items = payload["tasks"][0]["result"][0]["items"]
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
