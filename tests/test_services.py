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


# --- publish_service ---

async def test_create_blog_pr_includes_image_in_frontmatter():
    from services.publish_service import create_blog_pr
    from pathlib import Path
    from unittest.mock import AsyncMock, patch, call

    gh_calls = []

    async def fake_run_gh(*args):
        gh_calls.append(args)
        if "git/ref/heads/main" in args[1]:
            return "abc123"
        if "contents/" in args[1] and "-X" not in args:
            raise RuntimeError("404 Not Found")
        if args[0] == "pr":
            return "https://github.com/test/repo/pull/1"
        return ""

    with patch("services.publish_service._run_gh", side_effect=fake_run_gh):
        with patch("services.publish_service.settings") as mock_settings:
            mock_settings.gh_repo = "https://github.com/test/repo"
            result = await create_blog_pr(
                draft_path=Path("data/drafts/2026-05-01-test-slug.md"),
                category="Study Methods",
                title="Test Title",
                excerpt="Test excerpt.",
                body="# Hello\n\nWorld.",
                image_bytes=b"fake png bytes",
            )

    assert result == "https://github.com/test/repo/pull/1"

    # Check that image was pushed
    image_push_calls = [c for c in gh_calls if "contents/public/blog/test-slug.png" in str(c)]
    assert len(image_push_calls) == 1

    # Check that MDX contains heroImage
    mdx_push_calls = [c for c in gh_calls if "contents/src/content/blog/test-slug.mdx" in str(c)]
    assert len(mdx_push_calls) == 1


async def test_create_blog_pr_no_image_skips_push():
    from services.publish_service import create_blog_pr
    from pathlib import Path
    from unittest.mock import patch

    gh_calls = []

    async def fake_run_gh(*args):
        gh_calls.append(args)
        if "git/ref/heads/main" in args[1]:
            return "abc123"
        if "contents/" in args[1] and "-X" not in args:
            raise RuntimeError("404 Not Found")
        if args[0] == "pr":
            return "https://github.com/test/repo/pull/1"
        return ""

    with patch("services.publish_service._run_gh", side_effect=fake_run_gh):
        with patch("services.publish_service.settings") as mock_settings:
            mock_settings.gh_repo = "https://github.com/test/repo"
            await create_blog_pr(
                draft_path=Path("data/drafts/2026-05-01-test-slug.md"),
                category="Study Methods",
                title="Test Title",
                excerpt="Test excerpt.",
                body="# Hello",
            )

    # No image push should have happened
    image_push_calls = [c for c in gh_calls if "public/blog/" in str(c)]
    assert len(image_push_calls) == 0
