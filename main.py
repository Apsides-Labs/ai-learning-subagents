import argparse
import asyncio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft and Arc marketing agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py --mode setup       First-time setup
  uv run python main.py --mode weekly      Plan 4 articles
  uv run python main.py --mode article     Write the next planned article
  uv run python main.py --mode validate    Check external API auth
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["setup", "weekly", "article", "validate", "measure"],
        required=False,
        help="setup | weekly | article | validate | measure",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=28,
        help="Days of measurement data to include (default: 28). Used with --mode measure.",
    )
    parser.add_argument(
        "--mark-published",
        metavar="ARTICLE_ID",
        help="Mark a calendar entry as published. Requires --url.",
    )
    parser.add_argument(
        "--url",
        metavar="LIVE_URL",
        help="Canonical URL of the published article (used with --mark-published).",
    )
    return parser


async def _run_setup() -> None:
    from agents.orchestrator import run_setup
    print("Running setup: extracting product facts and crawling competitors...")
    await run_setup()
    print("Done. product_facts.md and competitor_profiles.md written to data/")
    print("Run --mode weekly next to plan articles.")


async def _run_weekly() -> None:
    from agents.orchestrator import run_weekly_batch
    print("Running weekly batch: market research → SEO → content calendar...")
    titles = await run_weekly_batch()
    print(f"\n{len(titles)} articles planned:")
    for i, title in enumerate(titles, 1):
        print(f"  {i}. {title}")
    print("\nRun --mode article to write each draft.")


async def _run_article() -> None:
    from agents.orchestrator import run_article
    from models.article import ArticleStatus
    print("Writing next planned article...")
    status, draft_path, pr_url = await run_article()
    if status is None:
        print("No planned articles in the content calendar.")
        print("Run --mode weekly first to populate the calendar.")
        return
    if status == ArticleStatus.ready_for_review:
        print(f"\nDraft ready for review: {draft_path}")
        print("Review, then publish to your blog and import to Medium with canonical URL.")
    else:
        print(f"\nDraft has flagged claims — review before publishing: {draft_path}")
        print("Fact-check flags appended to the end of the draft file.")
    if pr_url:
        print(f"\nBlog PR created: {pr_url}")


async def _run_validate() -> None:
    from agents.orchestrator import run_validate
    import sys
    exit_code = await run_validate()
    sys.exit(exit_code)


async def _run_measure(days: int) -> None:
    from agents.orchestrator import run_measure
    md_path, html_path = await run_measure(days=days)
    print(f"\nMeasurement brief written:")
    print(f"  Agent-facing (MD):  {md_path}")
    print(f"  Human dashboard:    {html_path}")


async def _run_mark_published(article_id: str, url: str) -> None:
    from services.calendar_service import mark_published
    if not url:
        raise SystemExit("--mark-published requires --url <canonical-url>")
    await mark_published(article_id, live_url=url)
    print(f"Marked {article_id!r} as published with URL {url}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mark_published:
        asyncio.run(_run_mark_published(args.mark_published, args.url or ""))
        return

    if not args.mode:
        parser.error("--mode is required unless --mark-published is given")

    if args.mode == "setup":
        asyncio.run(_run_setup())
    elif args.mode == "weekly":
        asyncio.run(_run_weekly())
    elif args.mode == "article":
        asyncio.run(_run_article())
    elif args.mode == "validate":
        asyncio.run(_run_validate())
    elif args.mode == "measure":
        asyncio.run(_run_measure(args.days))


if __name__ == "__main__":
    main()
