"""Google Search Console client.

google-api-python-client is sync-only. The public query_* methods are async
and wrap their sync helpers in asyncio.to_thread so the call doesn't block
the event loop.
"""

import asyncio
from datetime import date
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import settings


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _build_service():
    """Build a Search Console service client using the service-account credentials."""
    if not settings.google_application_credentials:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS must be set in .env")

    creds = service_account.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=SCOPES,
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


async def query_blog_performance(start_date: date, end_date: date) -> list[dict[str, Any]]:
    """Per-(page, query) performance over the window, filtered to /blog/ URLs.

    Returns rows with keys: page, query, clicks, impressions, ctr, position.

    Uses dataState='final' so the last ~2-3 days of unfinalized data are
    excluded. Callers should reflect this in the effective window header
    (start_date, end_date - 3 days) in user-facing output.
    """
    return await asyncio.to_thread(_query_blog_performance_sync, start_date, end_date)


def _query_blog_performance_sync(start_date: date, end_date: date) -> list[dict[str, Any]]:
    service = _build_service()
    request_body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page", "query"],
        "dimensionFilterGroups": [{
            "filters": [{
                "dimension": "page",
                "operator": "contains",
                "expression": "/blog/",
            }]
        }],
        "rowLimit": 25000,
        "dataState": "final",
    }
    response = service.searchanalytics().query(
        siteUrl=settings.gsc_site_url,
        body=request_body,
    ).execute()

    rows = []
    for row in response.get("rows", []):
        keys = row.get("keys", ["", ""])
        rows.append({
            "page": keys[0] if len(keys) > 0 else "",
            "query": keys[1] if len(keys) > 1 else "",
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0.0),
            "position": row.get("position", 0.0),
        })
    return rows


async def validate() -> tuple[bool, str]:
    """Cheap check: list sites the service account can see. Free, no quota cost."""
    try:
        return await asyncio.to_thread(_validate_sync)
    except Exception as exc:  # noqa: BLE001
        return False, f"GSC validate failed: {exc}"


def _validate_sync() -> tuple[bool, str]:
    service = _build_service()
    response = service.sites().list().execute()
    sites = [s.get("siteUrl", "") for s in response.get("siteEntry", [])]
    if not sites:
        return False, "Service account has no GSC properties — check permission grant."
    if settings.gsc_site_url not in sites:
        return False, (
            f"GSC_SITE_URL={settings.gsc_site_url!r} not in accessible properties: {sites}"
        )
    return True, f"GSC ok. Accessible properties: {sites}"
