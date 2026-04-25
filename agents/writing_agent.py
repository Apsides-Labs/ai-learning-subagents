import re
from datetime import datetime
from pathlib import Path

from chains.writing_chain import run_writing_chain
from models.article import ContentCalendarEntry
from output_schemas import ArticleOutput
from services.file_service import DRAFTS_DIR, write_text


def _remove_em_dashes(text: str) -> str:
    """Replace em dashes (with any surrounding spaces) with a comma and single space."""
    return re.sub(r'\s*—\s*', ', ', text)


def _build_frontmatter(article: ArticleOutput) -> str:
    return (
        "---\n"
        f"title: {article.title}\n"
        f"primary_keyword: {article.primary_keyword}\n"
        f"meta_description: {article.meta_description}\n"
        "status: draft\n"
        "---\n\n"
    )


async def run_writing_agent(
    entry: ContentCalendarEntry,
    product_facts: str,
) -> tuple[Path, ArticleOutput]:
    """Write one article. Returns (draft_path, ArticleOutput)."""
    article = await run_writing_chain(entry, product_facts)

    clean_content = _remove_em_dashes(article.markdown_content)

    slug = entry.id
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}-{slug}.md"
    draft_path = DRAFTS_DIR / filename

    full_content = _build_frontmatter(article) + clean_content
    await write_text(draft_path, full_content)

    return draft_path, article
