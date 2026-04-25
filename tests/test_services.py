import json
import pytest
from pathlib import Path
from models.article import ArticleStatus, ArticleType, ContentCalendarEntry


@pytest.fixture
def calendar_path(tmp_path: Path) -> Path:
    return tmp_path / "content_calendar.json"


@pytest.fixture
def entry() -> ContentCalendarEntry:
    return ContentCalendarEntry(
        id="test-article",
        title="Test Article",
        primary_keyword="test keyword",
        article_type=ArticleType.standard,
        target_audience="testers",
        angle="testing is good",
        meta_description="A test article.",
    )


# --- file_service ---

async def test_write_and_read_text(tmp_path: Path):
    from services.file_service import write_text, read_text
    p = tmp_path / "hello.md"
    await write_text(p, "# Hello")
    result = await read_text(p)
    assert result == "# Hello"


async def test_write_creates_parent_dirs(tmp_path: Path):
    from services.file_service import write_text
    p = tmp_path / "nested" / "deep" / "file.md"
    await write_text(p, "content")
    assert p.exists()


# --- calendar_service ---

async def test_load_empty_calendar(tmp_path: Path, monkeypatch):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    result = await calendar_service.load_calendar()
    assert result == []


async def test_add_and_load_entries(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    loaded = await calendar_service.load_calendar()
    assert len(loaded) == 1
    assert loaded[0].id == "test-article"


async def test_add_entries_deduplicates(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    await calendar_service.add_entries([entry])
    loaded = await calendar_service.load_calendar()
    assert len(loaded) == 1


async def test_next_planned_returns_first_planned(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    result = await calendar_service.next_planned()
    assert result is not None
    assert result.id == "test-article"


async def test_next_planned_returns_none_when_empty(tmp_path: Path, monkeypatch):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    result = await calendar_service.next_planned()
    assert result is None


async def test_update_status(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    await calendar_service.update_status("test-article", ArticleStatus.in_progress)
    loaded = await calendar_service.load_calendar()
    assert loaded[0].status == ArticleStatus.in_progress


async def test_update_status_with_draft_path(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    await calendar_service.update_status(
        "test-article", ArticleStatus.ready_for_review, draft_path="data/drafts/draft.md"
    )
    loaded = await calendar_service.load_calendar()
    assert loaded[0].draft_path == "data/drafts/draft.md"
