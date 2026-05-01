# Blog Image Generation — Design Spec

## Goal

Generate a hero image for each blog post using OpenAI's `gpt-image-2` model, and include it in the blog PR pushed to the draftnarc repo. Images are stored in GitHub (not Cloudflare), committed alongside the MDX file on the same branch. Existing posts without images fall back to the current `imageBg` color cards.

## Data Model Changes

### `ArticleOutput` (output_schemas.py)

Add two fields so the writing agent produces image-ready metadata alongside the article:

```python
class ArticleOutput(_StrictModel):
    title: str
    primary_keyword: str
    meta_description: str
    markdown_content: str
    article_summary: str   # 1-2 sentence summary of the article
    key_takeaway: str       # the single core idea readers should walk away with
```

### Blog content schema (draftnarc `src/content.config.ts`)

Add optional `heroImage` field:

```typescript
schema: z.object({
    title: z.string(),
    category: z.string(),
    excerpt: z.string(),
    date: z.string(),
    readTime: z.string(),
    imageBg: z.string(),
    heroImage: z.string().optional(),  // e.g. "/blog/tutorial-hell.png"
})
```

No changes to `ContentCalendarEntry`.

## Prompt Template

Move `draft-and-arc-blog-image-prompt.md` from repo root to `prompts/md/chains/blog_image.md`.

Strip the instructional wrapper (heading, "Replace:" instructions, example values, code fences). Keep only the raw prompt text with `{title}`, `{article_summary}`, `{key_takeaway}` placeholders. The prompt content itself stays word-for-word identical.

Delete the original file from repo root after the move.

## Image Service

New file: `services/image_service.py`

### `generate_blog_image(title, article_summary, key_takeaway) -> bytes | None`

1. Read the prompt template from `prompts/md/chains/blog_image.md`
2. Interpolate `{title}`, `{article_summary}`, `{key_takeaway}` using `.format()`
3. Call OpenAI's `client.images.generate()`:
   - `model="gpt-image-2"`
   - `size="1536x1024"`
   - Interpolated prompt
4. Return image as PNG bytes
5. On any failure (API error, rate limit, timeout): log a warning, return `None`

Uses `settings.openai_api_key`. No new env vars.

## Publish Service Changes

Modify `create_blog_pr()` in `services/publish_service.py`.

### New parameter

`image_bytes: bytes | None = None`

### Behavior

1. If `image_bytes is not None`:
   - Push image to `public/blog/{slug}.png` on the branch via GitHub Contents API (base64-encoded PUT, same pattern as the MDX push)
   - Include `heroImage: "/blog/{slug}.png"` in the MDX frontmatter
2. If `image_bytes is None`:
   - No image pushed, no `heroImage` in frontmatter
   - Everything works exactly as today (`imageBg` only)

### Order of operations

1. Get main branch SHA
2. Delete/create branch
3. Push image file (only if `image_bytes` provided)
4. Push MDX file (with or without `heroImage` in frontmatter)
5. Create PR

## Orchestrator Changes

Modify `run_article()` in `agents/orchestrator.py`.

After writing + fact-checking, before PR creation:

```python
image_bytes = None
if settings.gh_repo:
    image_bytes = await generate_blog_image(
        title=article.title,
        article_summary=article.article_summary,
        key_takeaway=article.key_takeaway,
    )

pr_url = await create_blog_pr(
    draft_path, entry.blog_category,
    title=article.title,
    excerpt=article.meta_description,
    body=article.markdown_content,
    image_bytes=image_bytes,
)
```

## Blog Template Changes (draftnarc repo)

### `src/pages/blog.astro` — card listing

The image area div (currently lines 47-57):
- If `post.data.heroImage` exists: render `<img src={post.data.heroImage} alt={post.data.title} />` with `object-fit: cover` filling the 200px area
- If not: keep current `imageBg` color + placeholder SVG unchanged

### `src/pages/blog/[slug].astro` — post hero

The hero div (currently lines 62-78):
- If `post.data.heroImage` exists: render `<img>` with `object-fit: cover` filling the 280px area, keep category badge overlay on top
- If not: keep current `imageBg` color + dot pattern + placeholder SVG unchanged

### `src/content.config.ts`

Add `heroImage: z.string().optional()` to the schema object.

## Failure Handling

Image generation is non-blocking. If it fails:
- `generate_blog_image()` returns `None`
- `create_blog_pr()` receives `None`, skips image push, omits `heroImage` from frontmatter
- PR is created with MDX only — blog renders with `imageBg` color fallback
- Warning is logged

## Writing Prompt Update

The writing prompt at `prompts/md/chains/writing.md` needs no structural changes. The `ArticleOutput` schema already drives what the LLM produces via `with_structured_output()`. Adding `article_summary` and `key_takeaway` to the Pydantic model is sufficient — the LLM will produce them based on the field names and type hints.

## Files Changed

### ai-learning-subagents repo
- `output_schemas.py` — add `article_summary`, `key_takeaway` to `ArticleOutput`
- `services/image_service.py` — new file
- `services/publish_service.py` — add `image_bytes` param, push image, conditional `heroImage` frontmatter
- `agents/orchestrator.py` — call `generate_blog_image()`, pass result to `create_blog_pr()`
- `prompts/md/chains/blog_image.md` — new file (moved from root)
- `draft-and-arc-blog-image-prompt.md` — deleted

### draftnarc repo
- `src/content.config.ts` — add optional `heroImage` field
- `src/pages/blog.astro` — conditional image rendering on cards
- `src/pages/blog/[slug].astro` — conditional image rendering on hero
