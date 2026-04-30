import asyncio
import base64
import math
import re
from datetime import datetime
from pathlib import Path

from config import settings


_BG_COLORS = ["#d5e0f5", "#ead5f5", "#ddd5f5", "#d5f0e4", "#e4d5f5", "#f5ead5", "#d5f5e0"]


async def _run_gh(*args: str) -> str:
    """Run a gh CLI command and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "gh", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {stderr.decode()}")
    return stdout.decode().strip()


async def create_blog_pr(
    draft_path: Path,
    category: str,
    title: str,
    excerpt: str,
    body: str,
) -> str:
    """Build .mdx from structured fields, push to the blog repo, and open a PR. Returns the PR URL."""
    repo = settings.gh_repo.strip().rstrip("/").removeprefix("https://github.com/")

    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", draft_path.stem)
    branch = f"blog/{slug}"
    blog_path = f"src/content/blog/{slug}.mdx"

    words = len(body.split())
    read_time = f"{max(1, math.ceil(words / 250))} min read"
    bg_color = _BG_COLORS[hash(slug) % len(_BG_COLORS)]
    date_str = datetime.now().strftime("%b %d, %Y")

    mdx_content = (
        f'---\ntitle: "{title}"\ncategory: "{category}"\n'
        f'excerpt: "{excerpt}"\ndate: "{date_str}"\n'
        f'readTime: "{read_time}"\nimageBg: "{bg_color}"\n---\n\n{body}\n'
    )

    default_branch_sha = await _run_gh(
        "api", f"repos/{repo}/git/ref/heads/main",
        "--jq", ".object.sha",
    )

    try:
        await _run_gh("api", f"repos/{repo}/git/refs/heads/{branch}", "-X", "DELETE")
    except RuntimeError as e:
        if "404" not in str(e) and "Reference does not exist" not in str(e):
            raise

    await _run_gh(
        "api", f"repos/{repo}/git/refs",
        "-f", f"ref=refs/heads/{branch}",
        "-f", f"sha={default_branch_sha}",
    )

    encoded = base64.b64encode(mdx_content.encode()).decode()
    put_args = [
        "api", f"repos/{repo}/contents/{blog_path}",
        "-X", "PUT",
        "-f", f"message=Add blog post: {slug}",
        "-f", f"content={encoded}",
        "-f", f"branch={branch}",
    ]
    try:
        existing_sha = await _run_gh(
            "api", f"repos/{repo}/contents/{blog_path}?ref={branch}",
            "--jq", ".sha",
        )
        put_args.extend(["-f", f"sha={existing_sha}"])
    except RuntimeError:
        pass  # File doesn't exist yet, no sha needed
    await _run_gh(*put_args)

    return await _run_gh(
        "pr", "create",
        "--repo", repo,
        "--base", "main",
        "--head", branch,
        "--title", f"Add blog post: {slug.replace('-', ' ').title()}",
        "--body", (
            "## Summary\n"
            f"- Auto-generated blog post from ai-learning-subagents pipeline\n"
            f"- Source draft: `{draft_path.name}`\n\n"
            "## Test plan\n"
            "- [ ] Verify post renders on blog listing page\n"
            "- [ ] Verify individual post page loads correctly\n"
        ),
    )
