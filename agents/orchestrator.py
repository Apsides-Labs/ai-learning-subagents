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
    existing_coverage = "\n".join(
        f"- {e.title} | primary: {e.primary_keyword} | secondary: {', '.join(e.secondary_keywords)}"
        for e in existing
    )

    research_context = competitor_profiles + "\n\n" + market_brief

    # Append measurement brief if it exists. The delimiter is structural —
    # the SEO system prompt's PAST-PERFORMANCE CONTEXT section looks for this exact header.
    if file_service.MEASUREMENT_BRIEF_MD_PATH.exists():
        measurement_brief = await file_service.read_text(file_service.MEASUREMENT_BRIEF_MD_PATH)
        research_context += "\n\n## MEASUREMENT BRIEF\n\n" + measurement_brief

    new_entries = await run_seo_agent(research_context, existing_ids, existing_coverage)
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


async def run_validate() -> int:
    """Cheap end-to-end validation of external integrations.

    Checks DataForSEO, GSC, and GA4. Returns 0 on full success, 1 if any
    check failed. Each check is independent — a missing credential must
    produce a clean [FAIL] line, not a Python traceback.
    """
    from services.dataforseo_client import get_client, DataForSEOClient
    from services import gsc_client, ga4_client

    results: list[tuple[str, bool, str]] = []

    # DataForSEO
    dfs_client: DataForSEOClient | None = None
    try:
        dfs_client = get_client()
        ok, message = await dfs_client.validate()
    except Exception as exc:  # noqa: BLE001
        ok, message = False, f"Could not construct client: {exc}"
    finally:
        if dfs_client is not None:
            try:
                await dfs_client.aclose()
            except Exception:  # noqa: BLE001
                pass
    results.append(("DataForSEO", ok, message))

    # GSC
    try:
        gsc_ok, gsc_message = await gsc_client.validate()
    except Exception as exc:  # noqa: BLE001
        gsc_ok, gsc_message = False, f"GSC validate threw: {exc}"
    results.append(("GSC", gsc_ok, gsc_message))

    # GA4
    try:
        ga4_ok, ga4_message = await ga4_client.validate()
    except Exception as exc:  # noqa: BLE001
        ga4_ok, ga4_message = False, f"GA4 validate threw: {exc}"
    results.append(("GA4", ga4_ok, ga4_message))

    all_ok = True
    for name, ok, message in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {message}")
        if not ok:
            all_ok = False

    return 0 if all_ok else 1


async def run_measure(days: int = 28) -> tuple[Path, Path]:
    """Run the measurement pipeline; write MD + HTML briefs. Returns the two paths."""
    from agents.measurement_agent import run_measurement_agent
    from renderers.measurement_md import render_md
    from renderers.measurement_html import render_html
    from services.dataforseo_client import get_client as get_dfs_client

    try:
        final = await run_measurement_agent(days=days)

        md = render_md(final)
        effective_note = "data finalized through " + final.report.window_end
        html = render_html(final, effective_end_note=effective_note)

        await file_service.atomic_write_text(file_service.MEASUREMENT_BRIEF_MD_PATH, md)
        await file_service.atomic_write_text(file_service.MEASUREMENT_BRIEF_HTML_PATH, html)
    finally:
        # Close the httpx AsyncClient on the singleton DFS client to avoid
        # 'unclosed transport' RuntimeWarning on process exit.
        try:
            await get_dfs_client().aclose()
        except Exception:  # noqa: BLE001
            pass

    return file_service.MEASUREMENT_BRIEF_MD_PATH, file_service.MEASUREMENT_BRIEF_HTML_PATH
