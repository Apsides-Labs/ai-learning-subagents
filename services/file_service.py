import os
import uuid
from pathlib import Path
import aiofiles

DATA_DIR = Path("data")
DRAFTS_DIR = DATA_DIR / "drafts"
PRODUCT_FACTS_PATH = DATA_DIR / "product_facts.md"
COMPETITOR_PROFILES_PATH = DATA_DIR / "competitor_profiles.md"
MARKET_BRIEF_PATH = DATA_DIR / "market_brief.md"
MEASUREMENT_BRIEF_MD_PATH = DATA_DIR / "measurement_brief.md"
MEASUREMENT_BRIEF_HTML_PATH = DATA_DIR / "measurement_brief.html"


async def read_text(path: Path) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return await f.read()


async def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)


async def atomic_write_text(path: Path, content: str) -> None:
    """Write text to `path` atomically.

    Writes to a sibling tmp file first, then `os.replace`s it onto the
    target. A crash mid-write leaves either the old file intact or
    nothing (if the target didn't exist before) — never a half-written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            await f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
