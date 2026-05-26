"""--mark-published sets status, published_at, and live_url atomically."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


async def test_mark_published_sets_three_fields(tmp_path: Path):
    """Round-trip: load, mark, save, reload — fields persist."""
    from services import calendar_service
    from models.article import ContentCalendarEntry, ArticleType, ArticleStatus

    calendar_path = tmp_path / "content_calendar.json"

    entries = [
        ContentCalendarEntry(
            id="tutorial-hell-progress",
            status=ArticleStatus.ready_for_review,
            title="...",
            primary_keyword="...",
            article_type=ArticleType.standard,
            target_audience="...",
            angle="...",
            meta_description="...",
        )
    ]
    calendar_path.write_text(json.dumps([e.model_dump() for e in entries], indent=2))

    with patch.object(calendar_service, "CALENDAR_PATH", calendar_path):
        await calendar_service.mark_published(
            "tutorial-hell-progress",
            live_url="https://www.draftandarc.com/blog/tutorial-hell-progress",
            published_on="2026-05-20",
        )
        reloaded = await calendar_service.load_calendar()

    target = next(e for e in reloaded if e.id == "tutorial-hell-progress")
    assert target.status == ArticleStatus.published
    assert target.published_at == "2026-05-20"
    assert target.live_url == "https://www.draftandarc.com/blog/tutorial-hell-progress"


async def test_mark_published_raises_on_missing_id(tmp_path: Path):
    from services import calendar_service

    calendar_path = tmp_path / "content_calendar.json"
    calendar_path.write_text("[]")

    with patch.object(calendar_service, "CALENDAR_PATH", calendar_path):
        with pytest.raises(ValueError, match="not found"):
            await calendar_service.mark_published(
                "nonexistent",
                live_url="https://www.draftandarc.com/blog/x",
            )
