import argparse
import asyncio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft and Arc marketing agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py --mode setup      First-time setup: extract product facts + crawl competitors
  uv run python main.py --mode weekly     Refresh market data + plan 4 articles
  uv run python main.py --mode article    Write the next planned article
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["setup", "weekly", "article"],
        required=True,
        help="setup: product facts + competitors | weekly: market refresh + SEO | article: write draft",
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


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mode == "setup":
        asyncio.run(_run_setup())
    elif args.mode == "weekly":
        asyncio.run(_run_weekly())
    elif args.mode == "article":
        asyncio.run(_run_article())


if __name__ == "__main__":
    main()
