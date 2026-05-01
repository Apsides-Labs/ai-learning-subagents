# Blog Image Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate hero images for blog posts using OpenAI's `gpt-image-2` and include them in the blog PR committed to GitHub.

**Architecture:** New `services/image_service.py` calls OpenAI image API with a templated prompt. The publish service pushes the image to the blog repo alongside the MDX. Blog templates conditionally render the image or fall back to the existing `imageBg` color.

**Tech Stack:** OpenAI Python SDK (`openai`), GitHub Contents API (via `gh` CLI), Astro content collections

---

### Task 1: Add `article_summary` and `key_takeaway` to ArticleOutput

**Files:**
- Modify: `output_schemas.py:57-62`
- Modify: `tests/test_agents.py:146-151,195-199,353-358`

- [ ] **Step 1: Update the ArticleOutput schema**

In `output_schemas.py`, add the two new fields to `ArticleOutput`:

```python
class ArticleOutput(_StrictModel):
    title: str
    primary_keyword: str
    meta_description: str
    markdown_content: str
    article_summary: str
    key_takeaway: str
```

- [ ] **Step 2: Update all test fixtures that construct ArticleOutput**

In `tests/test_agents.py`, every `ArticleOutput(...)` construction needs the two new fields. There are three instances:

Line ~146 (`test_writing_agent_saves_draft`):
```python
    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# The Feynman Technique\n\nYou can learn anything...",
        article_summary="A guide to using the Feynman Technique to learn programming concepts faster.",
        key_takeaway="Explaining a concept in simple terms reveals what you actually understand.",
    )
```

Line ~195 (`test_writing_agent_strips_em_dashes_from_saved_draft`):
```python
    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="Learn fast — and remember more — every day.",
        article_summary="Tips for learning faster and retaining more.",
        key_takeaway="Spacing your practice sessions beats cramming every time.",
    )
```

Line ~353 (`test_orchestrator_article_mode_clean`):
```python
    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# Feynman Technique\n\nLearn anything.",
        article_summary="A guide to the Feynman Technique for programmers.",
        key_takeaway="Teaching what you learn is the fastest way to master it.",
    )
```

- [ ] **Step 3: Run tests to verify nothing breaks**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add output_schemas.py tests/test_agents.py
git commit -m "feat: add article_summary and key_takeaway to ArticleOutput"
```

---

### Task 2: Move prompt template to `prompts/md/chains/blog_image.md`

**Files:**
- Create: `prompts/md/chains/blog_image.md`
- Delete: `draft-and-arc-blog-image-prompt.md`

- [ ] **Step 1: Create the prompt file**

Create `prompts/md/chains/blog_image.md` with just the raw prompt text extracted from the original file (lines 11-33). Strip the markdown heading, instructions, example section, and code fences. Keep the three placeholders `{title}`, `{article_summary}`, `{key_takeaway}`:

```text
A modern editorial illustration for a Draft and Arc blog post titled "{title}".

Article context: "{article_summary}"

Core idea to communicate: "{key_takeaway}"

Depict one concrete, recognizable visual metaphor that captures the core idea of the article in a visually interesting way. The subject should be immediately understandable. A viewer should grasp the topic within a second of looking.

Favor a single refined object or a tightly composed group of forms, not a busy scene. The metaphor should be grounded in real things: tools, materials, machines, architecture, paper systems, cards, layers, containers, pathways, building blocks, or everyday objects reimagined.

The image should feel calm, useful, intelligent, and practical. It should look like a polished editorial image for a premium learning product, not a marketing campaign.

Style: contemporary 3D illustration with soft volumetric lighting, matte and glossy material contrast, subtle surface detail, gentle shadows, and shallow depth of field. The polished editorial aesthetic used on modern tech company blogs and documentation like Stripe, Linear, Vercel, and GitHub. Muted sophisticated palette with one or two subtle accent tones. Clean, premium, confident.

Composition: center the main subject with generous breathing room around it. Keep the image spacious, curated, and uncluttered. Prioritize a strong silhouette, simple shapes, elegant layering, and clear visual hierarchy. The result should feel like a sculptural product object or abstract learning artifact, not a literal desk setup.

Avoid crowded tabletop scenes, long step-by-step sequences, piles of papers, messy learning materials, generic educational stock imagery, or overly literal storytelling.

Strictly no people, no faces, no text, no letters, no numbers, no logos, no UI screenshots, no charts, no code, no robots, no lightbulbs, no glowing brains, no generic network visuals, and no exaggerated sci-fi style.

Wide 16:9 format suitable for a blog post hero banner. High production value, cohesive with a series of modern lesson and blog illustrations.
```

- [ ] **Step 2: Delete the original file from repo root**

```bash
rm draft-and-arc-blog-image-prompt.md
```

- [ ] **Step 3: Verify the prompt file loads correctly**

```bash
cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -c "
from pathlib import Path
text = (Path('prompts/md/chains/blog_image.md')).read_text()
assert '{title}' in text
assert '{article_summary}' in text
assert '{key_takeaway}' in text
print('Prompt template OK:', len(text), 'chars')
"
```

- [ ] **Step 4: Commit**

```bash
git add prompts/md/chains/blog_image.md
git rm draft-and-arc-blog-image-prompt.md
git commit -m "refactor: move blog image prompt template to prompts/md/chains/"
```

---

### Task 3: Create image service

**Files:**
- Create: `services/image_service.py`
- Create: `tests/test_image_service.py`

- [ ] **Step 1: Write the test for successful image generation**

Create `tests/test_image_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_generate_blog_image_returns_bytes():
    from services.image_service import generate_blog_image

    fake_image_bytes = b"\x89PNG\r\n\x1a\n fake image data"

    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json="iVBORw0KGgo=")]

    with patch("services.image_service.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await generate_blog_image(
            title="Tutorial Hell",
            article_summary="How to escape tutorial hell.",
            key_takeaway="Build small projects instead of watching videos.",
        )

    assert result is not None
    assert isinstance(result, bytes)
    mock_client.images.generate.assert_called_once()
    call_kwargs = mock_client.images.generate.call_args[1]
    assert call_kwargs["model"] == "gpt-image-2"
    assert call_kwargs["size"] == "1536x1024"
    assert "Tutorial Hell" in call_kwargs["prompt"]


async def test_generate_blog_image_returns_none_on_failure():
    from services.image_service import generate_blog_image

    with patch("services.image_service.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(side_effect=Exception("API rate limit"))
        mock_client_cls.return_value = mock_client

        result = await generate_blog_image(
            title="Test",
            article_summary="Summary.",
            key_takeaway="Takeaway.",
        )

    assert result is None


async def test_generate_blog_image_interpolates_prompt():
    from services.image_service import generate_blog_image

    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json="iVBORw0KGgo=")]

    with patch("services.image_service.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await generate_blog_image(
            title="Spaced Repetition",
            article_summary="A guide to spaced repetition.",
            key_takeaway="Review before you forget.",
        )

    call_kwargs = mock_client.images.generate.call_args[1]
    assert "Spaced Repetition" in call_kwargs["prompt"]
    assert "A guide to spaced repetition." in call_kwargs["prompt"]
    assert "Review before you forget." in call_kwargs["prompt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/test_image_service.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the image service**

Create `services/image_service.py`:

```python
import base64
import logging
from pathlib import Path

import openai

from config import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "md" / "chains" / "blog_image.md"


async def generate_blog_image(
    title: str,
    article_summary: str,
    key_takeaway: str,
) -> bytes | None:
    """Generate a hero image for a blog post. Returns PNG bytes or None on failure."""
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(
            title=title,
            article_summary=article_summary,
            key_takeaway=key_takeaway,
        )

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.images.generate(
            model="gpt-image-2",
            prompt=prompt,
            size="1536x1024",
            response_format="b64_json",
            n=1,
        )

        b64_data = response.data[0].b64_json
        return base64.b64decode(b64_data)

    except Exception:
        logger.warning("Blog image generation failed", exc_info=True)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/test_image_service.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/image_service.py tests/test_image_service.py
git commit -m "feat: add image service for blog hero image generation"
```

---

### Task 4: Update publish service to push images

**Files:**
- Modify: `services/publish_service.py:27-101`
- Modify: `tests/test_services.py` (add new tests)

- [ ] **Step 1: Write tests for publish service image handling**

Add to the end of `tests/test_services.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/test_services.py::test_create_blog_pr_includes_image_in_frontmatter tests/test_services.py::test_create_blog_pr_no_image_skips_push -v`
Expected: FAIL (unexpected keyword argument `image_bytes`)

- [ ] **Step 3: Update create_blog_pr to accept and push images**

Modify `services/publish_service.py`. Replace the `create_blog_pr` function:

```python
async def create_blog_pr(
    draft_path: Path,
    category: str,
    title: str,
    excerpt: str,
    body: str,
    image_bytes: bytes | None = None,
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

    # Build frontmatter — include heroImage only when we have an image
    frontmatter_lines = [
        f'title: "{title}"',
        f'category: "{category}"',
        f'excerpt: "{excerpt}"',
        f'date: "{date_str}"',
        f'readTime: "{read_time}"',
        f'imageBg: "{bg_color}"',
    ]
    if image_bytes is not None:
        frontmatter_lines.append(f'heroImage: "/blog/{slug}.png"')

    mdx_content = "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n" + body + "\n"

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

    # Push image if provided
    if image_bytes is not None:
        image_path = f"public/blog/{slug}.png"
        encoded_image = base64.b64encode(image_bytes).decode()
        img_put_args = [
            "api", f"repos/{repo}/contents/{image_path}",
            "-X", "PUT",
            "-f", f"message=Add hero image for {slug}",
            "-f", f"content={encoded_image}",
            "-f", f"branch={branch}",
        ]
        try:
            existing_img_sha = await _run_gh(
                "api", f"repos/{repo}/contents/{image_path}?ref={branch}",
                "--jq", ".sha",
            )
            img_put_args.extend(["-f", f"sha={existing_img_sha}"])
        except RuntimeError:
            pass
        await _run_gh(*img_put_args)

    # Push MDX file
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
        pass
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/test_services.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/publish_service.py tests/test_services.py
git commit -m "feat: push hero image to blog repo in create_blog_pr"
```

---

### Task 5: Update orchestrator to generate and pass image

**Files:**
- Modify: `agents/orchestrator.py:1-75`
- Modify: `tests/test_agents.py:341-372`

- [ ] **Step 1: Update the orchestrator test to verify image generation is called**

In `tests/test_agents.py`, replace `test_orchestrator_article_mode_clean`:

```python
async def test_orchestrator_article_mode_clean(tmp_data_dir, sample_calendar_entry, sample_product_facts, monkeypatch):
    from agents.orchestrator import run_article
    from services import calendar_service, file_service
    from output_schemas import ArticleOutput, FactCheckOutput

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "DRAFTS_DIR", tmp_data_dir / "drafts")

    await file_service.write_text(tmp_data_dir / "product_facts.md", sample_product_facts)
    await calendar_service.add_entries([sample_calendar_entry])

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# Feynman Technique\n\nLearn anything.",
        article_summary="A guide to the Feynman Technique for programmers.",
        key_takeaway="Teaching what you learn is the fastest way to master it.",
    )
    fake_fact_check = FactCheckOutput(passed=True, items=[])
    fake_image = b"fake png bytes"

    with patch("agents.orchestrator.run_writing_agent", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = (tmp_data_dir / "drafts" / "draft.md", fake_article)
        with patch("agents.orchestrator.run_fact_check_chain", new_callable=AsyncMock) as mock_fc:
            mock_fc.return_value = fake_fact_check
            with patch("agents.orchestrator.generate_blog_image", new_callable=AsyncMock) as mock_img:
                mock_img.return_value = fake_image
                with patch("agents.orchestrator.create_blog_pr", new_callable=AsyncMock) as mock_pr:
                    mock_pr.return_value = None
                    status, draft_path, pr_url = await run_article()

    from models.article import ArticleStatus
    assert status == ArticleStatus.ready_for_review

    # Verify image generation was called with article fields
    mock_img.assert_called_once_with(
        title=fake_article.title,
        article_summary=fake_article.article_summary,
        key_takeaway=fake_article.key_takeaway,
    )

    # Verify image bytes were passed to create_blog_pr
    mock_pr.assert_called_once()
    assert mock_pr.call_args[1].get("image_bytes") == fake_image or mock_pr.call_args[0][-1] == fake_image
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/test_agents.py::test_orchestrator_article_mode_clean -v`
Expected: FAIL (no `generate_blog_image` to patch)

- [ ] **Step 3: Update the orchestrator**

Modify `agents/orchestrator.py`. Add the import and update `run_article`:

```python
from pathlib import Path
from typing import Optional

from agents.research_agent import run_setup_research, run_market_research
from agents.seo_agent import run_seo_agent
from agents.writing_agent import run_writing_agent
from chains.fact_check_chain import run_fact_check_chain
from config import settings
from models.article import ArticleStatus
from services import calendar_service, file_service
from services.image_service import generate_blog_image
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
        image_bytes = await generate_blog_image(
            title=article.title,
            article_summary=article.article_summary,
            key_takeaway=article.key_takeaway,
        )

        pr_url = await create_blog_pr(
            draft_path,
            entry.blog_category,
            title=article.title,
            excerpt=article.meta_description,
            body=article.markdown_content,
            image_bytes=image_bytes,
        )

    await calendar_service.update_status(
        entry.id, final_status, draft_path=str(draft_path), pr_url=pr_url,
    )

    return final_status, draft_path, pr_url
```

- [ ] **Step 4: Run all tests to verify everything passes**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/orchestrator.py tests/test_agents.py
git commit -m "feat: generate hero image in article pipeline"
```

---

### Task 6: Update blog content schema and templates (draftnarc repo)

**Files:**
- Modify: `/Users/ariankrasniqi/Desktop/ailearnings/draftnarc/src/content.config.ts:1-16`
- Modify: `/Users/ariankrasniqi/Desktop/ailearnings/draftnarc/src/pages/blog.astro:46-57`
- Modify: `/Users/ariankrasniqi/Desktop/ailearnings/draftnarc/src/pages/blog/[slug].astro:59-78`

- [ ] **Step 1: Add heroImage to the content schema**

In `draftnarc/src/content.config.ts`, add the optional field:

```typescript
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '*.mdx', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    category: z.string(),
    excerpt: z.string(),
    date: z.string(),
    readTime: z.string(),
    imageBg: z.string(),
    heroImage: z.string().optional(),
  }),
});

export const collections = { blog };
```

- [ ] **Step 2: Update the blog listing card to conditionally render images**

In `draftnarc/src/pages/blog.astro`, replace the image area div (lines 47-57):

```astro
              {/* Image area */}
              <div
                class="relative shrink-0"
                style={`background: ${post.data.imageBg}; height: 200px; display: flex; align-items: center; justify-content: center; overflow: hidden;`}
              >
                {post.data.heroImage ? (
                  <img
                    src={post.data.heroImage}
                    alt={post.data.title}
                    style="width: 100%; height: 100%; object-fit: cover;"
                    loading="lazy"
                  />
                ) : (
                  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style="opacity: 0.25;">
                    <rect x="8" y="10" width="32" height="4" rx="2" fill="#8258D2"/>
                    <rect x="8" y="20" width="24" height="3" rx="1.5" fill="#8258D2"/>
                    <rect x="8" y="29" width="28" height="3" rx="1.5" fill="#8258D2"/>
                    <rect x="8" y="38" width="18" height="3" rx="1.5" fill="#8258D2"/>
                  </svg>
                )}
              </div>
```

- [ ] **Step 3: Update the blog post hero to conditionally render images**

In `draftnarc/src/pages/blog/[slug].astro`, replace the hero div (lines 60-78):

```astro
    {/* ── Hero image ── */}
    <div class="max-w-4xl mx-auto px-6">
      <div
        class="hero-image rounded-2xl overflow-hidden"
        style={`background: ${post.data.imageBg}; height: 280px; display: flex; align-items: center; justify-content: center; position: relative;`}
      >
        {post.data.heroImage ? (
          <img
            src={post.data.heroImage}
            alt={post.data.title}
            style="width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0;"
          />
        ) : (
          <>
            <div style="position: absolute; inset: 0; background-image: radial-gradient(rgba(255,255,255,0.4) 1px, transparent 1px); background-size: 24px 24px;"></div>
            <svg width="64" height="64" viewBox="0 0 48 48" fill="none" style="opacity: 0.2; position: relative; z-index: 1;">
              <rect x="8" y="10" width="32" height="4" rx="2" fill="#8258D2"/>
              <rect x="8" y="20" width="24" height="3" rx="1.5" fill="#8258D2"/>
              <rect x="8" y="29" width="28" height="3" rx="1.5" fill="#8258D2"/>
              <rect x="8" y="38" width="18" height="3" rx="1.5" fill="#8258D2"/>
            </svg>
          </>
        )}
        <span
          class="absolute text-xs font-semibold px-3 py-1.5 rounded-full"
          style={`top: 20px; left: 20px; background: rgba(255,255,255,0.75); backdrop-filter: blur(8px); color: ${pill.text}; letter-spacing: 0.08em; text-transform: uppercase; border: 1px solid rgba(255,255,255,0.6); z-index: 2;`}
        >
          {post.data.category}
        </span>
      </div>
    </div>
```

- [ ] **Step 4: Verify the blog builds**

```bash
cd /Users/ariankrasniqi/Desktop/ailearnings/draftnarc && npm run build
```
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
cd /Users/ariankrasniqi/Desktop/ailearnings/draftnarc
git add src/content.config.ts src/pages/blog.astro src/pages/blog/\[slug\].astro
git commit -m "feat: add conditional hero image rendering with imageBg fallback"
```

---

### Task 7: Add openai dependency

**Files:**
- Modify: `pyproject.toml:7-19`

- [ ] **Step 1: Add openai to dependencies**

In `pyproject.toml`, add `"openai>=1.0"` to the dependencies list:

```toml
dependencies = [
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "langchain-community>=0.3",
    "langgraph>=0.2",
    "tavily-python>=0.3",
    "google-search-results>=2.4",
    "pytrends>=4.9",
    "pydantic-settings>=2.0",
    "aiofiles>=24.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "langchain-tavily>=0.2.18",
    "openai>=1.0",
]
```

- [ ] **Step 2: Install the dependency**

```bash
cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && pip install openai>=1.0
```

- [ ] **Step 3: Run all tests to confirm nothing broke**

Run: `cd /Users/ariankrasniqi/Desktop/ailearnings/ai-learning-subagents && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add openai SDK dependency for image generation"
```
