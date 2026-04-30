from pathlib import Path
from typing import Optional

from agents.research_agent import run_setup_research, run_market_research
from agents.seo_agent import run_seo_agent
from agents.writing_agent import run_writing_agent
from chains.fact_check_chain import run_fact_check_chain
from config import settings
from models.article import ArticleStatus
from services import calendar_service, file_service
from services.publish_service import create_blog_pr


async def run_setup() -> None:
    """Extract product facts + crawl competitors. Run once, or when product/competitors change."""
    product_facts, competitor_profiles = await run_setup_research(settings.codebase_path)
    await file_service.write_text(file_service.PRODUCT_FACTS_PATH, product_facts)
    await file_service.write_text(file_service.COMPETITOR_PROFILES_PATH, competitor_profiles)


async def run_weekly_batch() -> list[str]:
    """Refresh market data + plan 4 articles. Returns planned article titles."""
    if not file_service.PRODUCT_FACTS_PATH.exists() or not file_service.COMPETITOR_PROFILES_PATH.exists():
        await run_setup()

    competitor_profiles = await file_service.read_text(file_service.COMPETITOR_PROFILES_PATH)
    market_brief = await run_market_research(competitor_profiles)
    await file_service.write_text(file_service.MARKET_BRIEF_PATH, market_brief)

    existing = await calendar_service.load_calendar()
    existing_ids = {e.id for e in existing}

    research_context = competitor_profiles + "\n\n" + market_brief
    new_entries = await run_seo_agent(research_context, existing_ids)
    await calendar_service.add_entries(new_entries)

    return [e.title for e in new_entries]


async def run_article() -> tuple[Optional[ArticleStatus], Optional[Path], Optional[str]]:
    """Write the next planned article. Returns (final_status, draft_path, pr_url) or (None, None, None)."""
    entry = await calendar_service.next_planned()
    if entry is None:
        return None, None, None

    await calendar_service.update_status(entry.id, ArticleStatus.in_progress)
    product_facts = await file_service.read_text(file_service.PRODUCT_FACTS_PATH)
    draft_path, article = await run_writing_agent(entry, product_facts)
    fact_check = await run_fact_check_chain(product_facts, article.markdown_content)

    if fact_check.passed:
        final_status = ArticleStatus.ready_for_review
    else:
        final_status = ArticleStatus.needs_review_flagged
        flag_lines = ["\n\n---\n\n## FACT-CHECK FLAGS\n"]
        for item in fact_check.items:
            flag_lines.append(f"- **{item.verdict}**: {item.source_sentence}")
        existing_content = await file_service.read_text(draft_path)
        await file_service.write_text(draft_path, existing_content + "\n".join(flag_lines))

    pr_url = None
    if settings.gh_repo:
        pr_url = await create_blog_pr(
            draft_path,
            entry.blog_category,
            title=article.title,
            excerpt=article.meta_description,
            body=article.markdown_content,
        )

    await calendar_service.update_status(
        entry.id, final_status, draft_path=str(draft_path), pr_url=pr_url,
    )

    return final_status, draft_path, pr_url
