import json
from pathlib import Path
from typing import Optional
import aiofiles
from models.article import ArticleStatus, ContentCalendarEntry
from services.file_service import atomic_write_text

CALENDAR_PATH = Path("data/content_calendar.json")


async def load_calendar() -> list[ContentCalendarEntry]:
    if not CALENDAR_PATH.exists():
        return []
    async with aiofiles.open(CALENDAR_PATH, "r", encoding="utf-8") as f:
        data = json.loads(await f.read())
    return [ContentCalendarEntry(**entry) for entry in data]


async def save_calendar(entries: list[ContentCalendarEntry]) -> None:
    content = json.dumps([e.model_dump() for e in entries], indent=2)
    await atomic_write_text(CALENDAR_PATH, content)


async def add_entries(new_entries: list[ContentCalendarEntry]) -> None:
    entries = await load_calendar()
    existing_ids = {e.id for e in entries}
    for entry in new_entries:
        if entry.id not in existing_ids:
            entries.append(entry)
    await save_calendar(entries)


async def next_planned() -> Optional[ContentCalendarEntry]:
    entries = await load_calendar()
    return next((e for e in entries if e.status == ArticleStatus.planned), None)


async def update_status(
    entry_id: str,
    status: ArticleStatus,
    draft_path: Optional[str] = None,
    pr_url: Optional[str] = None,
) -> None:
    entries = await load_calendar()
    for entry in entries:
        if entry.id == entry_id:
            entry.status = status
            if draft_path is not None:
                entry.draft_path = draft_path
            if pr_url is not None:
                entry.pr_url = pr_url
    await save_calendar(entries)


from datetime import date as _date_module


async def mark_published(
    entry_id: str,
    *,
    live_url: str,
    published_on: Optional[str] = None,
) -> None:
    """Set status=published, published_at, and live_url on one calendar entry.

    `published_on` defaults to today's ISO date.
    Raises ValueError if `entry_id` is not in the calendar.
    """
    entries = await load_calendar()
    target = next((e for e in entries if e.id == entry_id), None)
    if target is None:
        raise ValueError(f"Calendar entry {entry_id!r} not found")

    target.status = ArticleStatus.published
    target.published_at = published_on or _date_module.today().isoformat()
    target.live_url = live_url

    await save_calendar(entries)
