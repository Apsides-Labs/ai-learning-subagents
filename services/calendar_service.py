import json
from pathlib import Path
from typing import Optional
import aiofiles
from models.article import ArticleStatus, ContentCalendarEntry

CALENDAR_PATH = Path("data/content_calendar.json")


async def load_calendar() -> list[ContentCalendarEntry]:
    if not CALENDAR_PATH.exists():
        return []
    async with aiofiles.open(CALENDAR_PATH, "r", encoding="utf-8") as f:
        data = json.loads(await f.read())
    return [ContentCalendarEntry(**entry) for entry in data]


async def save_calendar(entries: list[ContentCalendarEntry]) -> None:
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(CALENDAR_PATH, "w", encoding="utf-8") as f:
        await f.write(json.dumps([e.model_dump() for e in entries], indent=2))


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
) -> None:
    entries = await load_calendar()
    for entry in entries:
        if entry.id == entry_id:
            entry.status = status
            if draft_path is not None:
                entry.draft_path = draft_path
    await save_calendar(entries)
