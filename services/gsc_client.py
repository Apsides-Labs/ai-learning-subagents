"""Google Search Console client.

google-api-python-client is sync-only. The public query_* methods are async
and wrap their sync helpers in asyncio.to_thread so the call doesn't block
the event loop.

Auth strategy:
  - If GOOGLE_APPLICATION_CREDENTIALS points at a service-account JSON, use it.
  - Otherwise, fall back to Application Default Credentials (ADC). The user
    has typically run `gcloud auth application-default login` and granted
    their own account access to the GSC property. This is the path used when
    the Workspace org policy `iam.disableServiceAccountKeyCreation` blocks
    service-account JSON keys.
"""

import asyncio
from datetime import date
from typing import Any

import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import settings


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _build_service():
    """Build a Search Console service client.

    Prefers service-account JSON when GOOGLE_APPLICATION_CREDENTIALS is set
    AND the file actually exists; otherwise uses Application Default
    Credentials.
    """
    import os

    creds_path = settings.google_application_credentials
    if creds_path and os.path.isfile(creds_path):
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES,
        )
    else:
        # ADC: picks up `gcloud auth application-default login` credentials
        # from ~/.config/gcloud/application_default_credentials.json
        creds, _project = google.auth.default(scopes=SCOPES)

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
        return False, "No GSC properties accessible — check that your account / service account has access."
    if settings.gsc_site_url not in sites:
        return False, (
            f"GSC_SITE_URL={settings.gsc_site_url!r} not in accessible properties: {sites}"
        )
    return True, f"GSC ok. Accessible properties: {sites}"
