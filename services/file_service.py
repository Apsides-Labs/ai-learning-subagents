from pathlib import Path
import aiofiles

DATA_DIR = Path("data")
DRAFTS_DIR = DATA_DIR / "drafts"
PRODUCT_FACTS_PATH = DATA_DIR / "product_facts.md"
COMPETITOR_PROFILES_PATH = DATA_DIR / "competitor_profiles.md"
MARKET_BRIEF_PATH = DATA_DIR / "market_brief.md"


async def read_text(path: Path) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return await f.read()


async def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
