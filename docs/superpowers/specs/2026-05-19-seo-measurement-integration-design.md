# SEO Measurement Integration — Design

- **Date**: 2026-05-19
- **Status**: Draft (awaiting user review)
- **Scope**: DataForSEO integration + GSC/GA4 measurement + SEO playbook. Defers article-quality upgrades and the 10-article content batch to follow-up sessions.
- **Related docs**: `docs/superpowers/specs/2026-04-24-marketing-agents-design.md` (the original marketing-agents design this builds on).

---

## 1. Context and motivation

The existing marketing-agent system (`setup` → `weekly` → `article`) plans and drafts articles, but it is **blind to outcomes**. Once a draft is published to `https://www.draftandarc.com/blog`, the system has no way to know whether the article ranks, gets impressions, attracts clicks, or converts. Every weekly batch therefore makes the same kinds of choices regardless of what worked last week.

This design adds the **measurement spine** that closes the loop:

- Replace SerpAPI + pytrends with **DataForSEO** as the single source of SEO data (real keyword volume, difficulty, SERP, ranked-keywords for our domain).
- Add **Google Search Console (GSC)** and **Google Analytics 4 (GA4)** integrations to read real performance data for published articles.
- Add a new **`--mode measure`** that produces a dual-output brief (markdown for the SEO agent, HTML dashboard for the human).
- Wire the brief back into the next weekly batch so the SEO agent's keyword selection is informed by past performance.
- Ship a hand-written **SEO playbook** so the human operator (currently new to SEO) understands what the system is doing and how to interpret its outputs.

Quality upgrades to article generation and a 10-article content batch are explicitly **out of scope** for this design. They are intentionally deferred because once measurement is in place, those decisions will have evidence behind them.

---

## 2. Decisions made during brainstorming

These are the architectural decisions locked in during the brainstorming session, recorded so future implementers (and future-you) understand the *why*.

| Decision | Choice | Rationale |
|---|---|---|
| Session scope | Design DataForSEO + GA4/GSC + playbook only | Measurement is the spine; quality and content batch are downstream of having real data. |
| Publishing target | Own domain (`draftandarc.com/blog`) with canonical from Medium | Unlocks full GSC + GA4 + DataForSEO ranked-keywords visibility. |
| Measurement APIs | Both GSC and GA4 | GSC is the SEO truth source (queries, impressions, position, CTR). GA4 layers engagement and conversion. |
| Tool strategy | Replace SerpAPI + pytrends with DataForSEO; keep Tavily for `research_agent` | One bill, richer data; Tavily stays best-in-class for free-form pain mining. |
| Feedback loop | Hybrid: human-readable brief + auto-fed to next SEO agent run | Avoids both the "carry all strategy in your head" failure and the "automate decisions before evidence" failure. |
| Code shape | Approach A — tool-centric, minimal restructure | Smallest diff, independently shippable, easy to revert per piece. |
| Brief output | Dual output (MD for agent, HTML for human) from a single typed report | Each renderer projects only what its audience needs. |
| Metric education | HTML only (glossary, descriptions, GOOD/BORDERLINE/POOR badges) | The agent reasons fine over raw numbers; humans need vocabulary. |

---

## 3. Architecture and data flow

The system grows from a 3-mode pipeline to a 4-mode flywheel:

```
                ┌───────────────────────────────────────────┐
                │                  setup                    │
                │  (product facts + competitor profiles)    │
                └───────────────────┬───────────────────────┘
                                    │
                                    ▼
   ┌────────────────────────────────────────────────────────────┐
   │                          weekly                            │
   │                                                            │
   │   research_agent ──► market_brief.md                       │
   │       (Tavily — Reddit/HN pain mining, unchanged)          │
   │                                                            │
   │   seo_agent      ──► +4 calendar entries                   │
   │       (DataForSEO: SERP + volume + difficulty +            │
   │        ranked-keywords; reads measurement_brief.md)        │
   └───────────────────┬────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │              article                 │
        │  writing_agent + fact_check          │
        │  → draft.md → human review → publish │
        └──────────────────┬───────────────────┘
                           │  (you publish to draftandarc.com/blog)
                           ▼
   ┌────────────────────────────────────────────────────────────┐
   │                  measure  (NEW)                            │
   │                                                            │
   │   measurement_agent reads:                                 │
   │     • GSC API   → impressions/clicks/position/queries      │
   │     • GA4 API   → engagement/conversions per URL           │
   │     • DataForSEO Labs → ranked keywords for our domain     │
   │                                                            │
   │   writes:  data/measurement_brief.md   (for SEO agent)     │
   │            data/measurement_brief.html (for human)         │
   └────────────────────────────────────────────────────────────┘
```

### Key invariants

- Each mode is independently runnable. `measure` is read-only on external systems and safe to run anytime.
- `measurement_brief.md` is the *single* artifact connecting measurement back to planning — same pattern as `market_brief.md` today.
- Tavily stays only in `research_agent` (where open-ended crawl matters). DataForSEO is the sole SEO-data source for `seo_agent`.
- All three external APIs (DataForSEO, GSC, GA4) go through thin clients in `services/`, wrapped by `@tool` functions where agents need them — same pattern as `tools.py` today.
- A `CostTracker` in `services/dataforseo_client.py` enforces per-run cost and call-count caps so a bug cannot exhaust the $50 DataForSEO budget.

### Files added or changed

**New**:
- `services/dataforseo_client.py` — auth, HTTP, cost tracking
- `services/gsc_client.py` — Search Console auth + queries
- `services/ga4_client.py` — GA4 Data API auth + queries
- `services/scoring.py` — metric→label thresholds (HTML-only consumer)
- `tools/__init__.py`, `tools/dataforseo.py` — `@tool` wrappers for SEO agent (replaces top-level `tools.py` for new tools; existing `tools.py` retained)
- `agents/measurement_agent.py` — orchestrates GSC + GA4 + DFS Labs into the report
- `renderers/__init__.py`, `renderers/measurement_md.py`, `renderers/measurement_html.py`
- `renderers/templates/measurement.html.j2` — Jinja2 template (single self-contained HTML, CSS inlined)
- `prompts/md/agents/measurement_system.md`, `prompts/md/chains/measurement_synthesis.md`
- `tests/fixtures/*.json` — realistic API response samples
- `docs/playbooks/seo/` — the 7-doc playbook (see Section 9)

**Changed**:
- `agents/seo_agent.py` — new tool list (DataForSEO tools), reads `measurement_brief.md` from context
- `agents/orchestrator.py` — appends `measurement_brief.md` to SEO agent context when present; adds `run_measure()` entry point; adds `mark_published(article_id)` helper
- `prompts/md/agents/seo_system.md` — updated `TOOLS` section and new `PAST-PERFORMANCE CONTEXT` section
- `chains/seo_synthesis.md` — mentions DataForSEO metric names (volume, difficulty)
- `services/file_service.py` — add `MEASUREMENT_BRIEF_MD_PATH` and `MEASUREMENT_BRIEF_HTML_PATH`
- `output_schemas.py` — `MetricScore`, `QueryRow`, `ScoredArticlePerformance`, `MeasurementActionOutput`, `MeasurementBriefOutput`
- `main.py` — adds `--mode measure [--days N]`, `--mode validate`, `--mark-published <id>`
- `config.py` + `.env.example` — `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `GOOGLE_APPLICATION_CREDENTIALS`, `GSC_SITE_URL`, `GA4_PROPERTY_ID`, optional cost-cap overrides
- `pyproject.toml` — add `google-auth`, `google-api-python-client`, `google-analytics-data`, `jinja2`. Remove `google-search-results` (SerpAPI) and `pytrends`
- `tools.py` — remove the now-orphaned `people_also_ask` (SerpAPI) and `google_trends` (pytrends) `@tool` functions. The `research_agent` tools (`tavily_search_tool`, `jina_reader`, `list_codebase_files`, `read_codebase_file`) stay. SEO-agent tools live in the new `tools/dataforseo.py`.
- `tests/test_tools.py` — remove the `test_google_trends_*` tests; they reference deleted functions.
- `Makefile` — add `measure`, `validate` targets
- `CLAUDE.md` — pointer to `docs/playbooks/seo/00-overview.md`

---

## 4. DataForSEO endpoint plan and cost model

DataForSEO is sprawling. We use exactly five endpoints, at distinct decision points.

### Endpoints used

| Endpoint | Purpose | Approx. cost | Where called |
|---|---|---|---|
| SERP / Google / Organic / Live Advanced | Real SERP for one query (top 10 + PAA + related searches in one response) | ~$0.002/query | `seo_agent` — replaces Tavily-as-SERP and SerpAPI PAA |
| Keywords Data / Google Ads / Search Volume | Real monthly volume + CPC + competition (bulk, up to 1000 kw/call) | ~$0.05/1000 kw | `seo_agent` — bulk-score candidate keywords |
| Labs / Google / Bulk Keyword Difficulty | 0–100 difficulty score (bulk) | ~$0.01/1000 kw | `seo_agent` — filter unreachable terms |
| Labs / Google / Keyword Suggestions | Long-tail variants for a seed | ~$0.01/task | `seo_agent` — replaces pytrends-as-expansion |
| Labs / Google / Ranked Keywords for Domain | All keywords our domain currently ranks for (position, volume, URL) | ~$0.02/task | `measurement_agent` — closes the loop |

Prices are accurate to the public rate card as of 2026-05-19. The implementation step will re-verify against the live page and update this table if needed.

### Endpoint-to-tool mapping

DataForSEO exposes raw endpoints. The agent calls higher-level `@tool` functions that wrap them. Two of the tools are 1:1 wrappers; one bundles the two bulk endpoints since they are always used together.

| `@tool` function in `tools/dataforseo.py` | Wraps endpoint(s) |
|---|---|
| `dfs_serp_live_advanced(query)` | SERP / Google / Organic / Live Advanced |
| `dfs_keyword_suggestions(seed)` | Labs / Google / Keyword Suggestions |
| `dfs_bulk_keyword_data(keywords)` | Keywords Data / Search Volume **+** Labs / Bulk Keyword Difficulty (one call per endpoint, results merged) |
| `dfs_ranked_keywords_for_site(site)` | Labs / Google / Ranked Keywords for Domain (called only by `measurement_agent`, not exposed to `seo_agent`) |

### Endpoints explicitly NOT used

Backlinks API, On-Page API, Content Analysis API, App Data API, Reviews API, Merchant API, Domain Analytics — all out of scope.

### SEO agent flow with new endpoints (one weekly batch)

```
For each of 4 content opportunities from market_brief:
  1. Generate 3–6 candidate keywords (LLM, no API call)
  2. ONE keyword_suggestions call on the seed  →  adds 2–4 long-tail variants
  3. Bulk search_volume + keyword_difficulty   →  filters obviously bad candidates
  4. serp_live_advanced on top 2–3 survivors   →  SERP + PAA in one shot
  5. Synthesis LLM picks the final 4 article plans
```

### Cost model

| Activity | Approx. cost |
|---|---|
| Weekly SEO batch (12 candidates, 4 opportunities) | $0.07 |
| Weekly measure (1 ranked-keywords call) | $0.02 |
| **Combined weekly** | **~$0.10** |

$50 funds roughly **one year of weekly batches plus weekly measurement runs** with substantial headroom for ad-hoc experimentation.

### Cost guardrails

The real risk is not the budget; it is a bug. Two limits in `services/dataforseo_client.py`:

- `MAX_COST_PER_RUN = $1.00` — hard cap per `main.py` invocation. 50× normal usage.
- `MAX_CALLS_PER_RUN = 50` — hard cap on API calls per `main.py` invocation.

Both raise `DataForSEOBudgetExceeded`. Overridable via `DATAFORSEO_MAX_COST_PER_RUN` and `DATAFORSEO_MAX_CALLS_PER_RUN` env vars for explicit large runs.

### Auth

HTTP Basic with `login:password` (account email + API password from the DataForSEO dashboard). Stored in `.env` as `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`. Validated at client init.

---

## 5. GSC and GA4 setup and data plan

Both Google APIs use the same auth pattern (service account JSON), so one Google Cloud project covers both.

### One-time manual setup (operator does this)

1. **Google Cloud project**: create `draftandarc-seo-measurement` at `console.cloud.google.com`.
2. **Enable two APIs**: *Google Search Console API* and *Google Analytics Data API*.
3. **Create a service account**: `seo-measurement@<project>.iam.gserviceaccount.com`. Download the JSON key. Save it at `~/.config/draftandarc/gcp-service-account.json` (outside the repo). Reference via `GOOGLE_APPLICATION_CREDENTIALS` in `.env`.
4. **Grant the service account access to GSC**: in Search Console → Settings → Users and permissions → add the service account email as a *Restricted* user on the `sc-domain:draftandarc.com` property.
5. **Grant the service account access to GA4**: in GA4 → Admin → Property access management → add the service account email with *Viewer* role on the Draft and Arc property. Note the numeric property ID (e.g., `123456789`) for `GA4_PROPERTY_ID` in `.env`.

A step-by-step checklist with screenshot placeholders lives in `docs/playbooks/seo/05-gsc-ga4-setup.md`.

### Python libraries added

- `google-auth>=2.0` (shared)
- `google-api-python-client>=2.0` (for GSC; no first-party client library exists)
- `google-analytics-data>=0.18` (official GA4 client)

### What we ask GSC for

One method on `services/gsc_client.py`:

```python
async def query_blog_performance(start_date: date, end_date: date) -> list[GSCRow]:
    # dimensions: [page, query]
    # metrics:    clicks, impressions, ctr, position
    # rowLimit:   25000  (GSC max per call)
    # dimensionFilterGroups: page CONTAINS "/blog/"
    ...
```

One API call per measurement run. Returns "for every published article, which queries surfaced it, at what position, with what CTR." That is the SEO truth.

### What we ask GA4 for

One method on `services/ga4_client.py`:

```python
async def query_blog_engagement(start_date: date, end_date: date) -> list[GA4Row]:
    # dimensions: [pagePath, sessionSourceMedium]
    # metrics:    activeUsers, engagedSessions, averageSessionDuration,
    #             eventCount (filtered to event_name = "signup_cta_click")
    # dimensionFilter: pagePath CONTAINS "/blog/"
    ...
```

Source/medium dimension lets the brief separate organic-Google traffic from referral/social. The `signup_cta_click` event is the only conversion event wired in v1.

### Out-of-scope follow-up

The blog template currently does not fire a `signup_cta_click` event. Adding a one-line `gtag('event', 'signup_cta_click', { article_slug })` on the CTA link is needed to make the engagement-to-conversion measurement meaningful. Flagged in `docs/playbooks/seo/04-measurement-cheatsheet.md` as a known gap.

### Persistence and date window

- **Ephemeral**: raw GSC and GA4 responses (not stored — free to re-query, changes daily).
- **Persisted**: only the synthesized `data/measurement_brief.{md,html}`. Re-running `--mode measure` overwrites them.
- **Default window**: trailing 28 days. Overridable via `--mode measure --days 90`.

### Failure modes

- Service account lacks property access → 403 with a message pointing to the playbook setup step.
- New site with no GSC data yet → empty rows; brief says "no GSC data yet — Search Console needs ~2–3 days after first index" instead of an error.
- GA4 property has no data → same friendly empty-state.
- Any single integration failing never blocks the whole brief; the failing section displays an explanatory note while the rest renders normally.

---

## 6. `--mode measure` and the dual-output brief

### Command

```
uv run python main.py --mode measure                 # last 28 days
uv run python main.py --mode measure --days 90       # custom window
```

### Agent shape — hybrid deterministic + LLM

`agents/measurement_agent.py` (same pattern as `research_agent` → synthesis chain):

```
1. Load published-status entries from content_calendar.json
2. Parallel fetch (asyncio.gather):
     • GSC: query_blog_performance(start, end)
     • GA4: query_blog_engagement(start, end)
     • DFS Labs: ranked_keywords_for_site("draftandarc.com/blog")
3. Deterministic aggregation:
     • Per-article rollups (impressions, clicks, position, engagement)
     • Domain-level headline numbers
     • Gap analysis: ranked_keywords ∖ targeted_keywords
4. LLM synthesis (measurement_synthesis chain):
     • Writes per-article verdict + recommended actions
     • Context: calendar entries + raw aggregated data + product_facts
     • Output: MeasurementBriefOutput schema
5. Render:
     • renderers/measurement_md.py   → data/measurement_brief.md
     • renderers/measurement_html.py → data/measurement_brief.html
```

The split matters: **data collection is deterministic** (no LLM hallucination about numbers), **interpretation is LLM** (judgment about what to do).

### `data/measurement_brief.md` (agent-only)

Terse, no glossary, no scoring badges, no metric definitions:

```markdown
## Measurement Brief — 2026-05-19
Window: 2026-04-21 to 2026-05-19 (28 days)

### Headline
- Articles published: 4
- Impressions: 1,234 | Clicks: 56 | CTR: 4.5% | Avg position: 18.4
- Articles with 0 impressions in window: 1

### Per-article performance

#### tutorial-hell-progress (published 2026-04-27)
URL: /blog/tutorial-hell-progress
- GSC: 800 impr | 32 clicks | 4.0% CTR | pos 12.3
- GA4: 24 organic-Google users | 1:42 avg engagement | 0 signup_cta_click
- Top surfacing queries:
  - "how to get rid of tutorial hell" — 142 impr / 8 clicks / pos 9.2
  - "stop watching tutorials" — 89 impr / 3 clicks / pos 14.1
  - "tutorial hell programming" — 67 impr / 1 click / pos 21.4
- Verdict: borderline ranking, CTR below expected for position — title rewrite candidate

[... remaining published articles ...]

### Domain-level gap opportunities
DFS Labs sees us ranking for 47 keywords. Notable ones we did NOT target:
- "tutorial hell python" — pos 28, volume 90 — easy follow-up
- "how to escape tutorial hell" — pos 41, volume 320 — angle variant

### Recommended actions
1. HIGH: Refresh tutorial-hell-progress title/H1. CTR at 4% is below ~6% expected at position 12.
2. MEDIUM: Write follow-up "tutorial hell python" — already ranking #28 without targeting.
3. HIGH: anki-review-queue-burnout has 0 impressions 14 days post-publish. Verify indexing in GSC URL Inspection before assuming the angle is wrong.

### Coverage note
GSC data starts 2026-04-27 (first indexing date).
GA4 signup_cta_click event not yet wired — engagement-only.
```

### `data/measurement_brief.html` (human-only)

Same data, with:

- Glossary section at top defining every metric in plain English.
- Per-article cards with colored badges using `services/scoring.py`:
  - `.badge-good { background: #16a34a; color: #fff }`
  - `.badge-borderline { background: #f59e0b }`
  - `.badge-poor { background: #dc2626; color: #fff }`
- Inline `<details>` foldables for "why this metric matters" so cards stay scannable.
- Recommended actions ranked by priority with priority-colored left borders.
- Single self-contained file: CSS inlined, no JavaScript, no external dependencies. Emailable, archivable, works offline.

### Scoring thresholds (HTML only)

`services/scoring.py` exposes pure functions: `score_position(p) -> Label`, etc.

| Metric | GOOD | BORDERLINE | POOR | Reasoning |
|---|---|---|---|---|
| Avg position | 1–3 | 4–10 | 11+ | 1–3 = top of page 1 (real traffic). 4–10 = page 1 but most clicks go to top 3. 11+ = page 2, effectively no organic clicks. |
| CTR vs position | matches expected | within 50% | <50% of expected | Expected CTR per position: pos 1 ≈ 28%, pos 3 ≈ 11%, pos 10 ≈ 3%, pos 15 ≈ 1.5%. Low CTR at decent position = title/meta needs rewriting. |
| Impressions (post-publish) | 100+ in 28d | 10–99 | <10 after 14+ days | <10 impressions usually means indexing issue or zero demand — different fixes. |
| Engagement time (GA4) | 2:00+ | 0:30–2:00 | <0:30 | 1400-word article = ~5–7 min read. <30s = bounce before reading. 2min+ = actually read. |
| CTA click rate | 2%+ | 0.5–2% | <0.5% | Industry baseline for content-CTA conversion is 1–3%. Below 0.5% means CTA isn't compelling or doesn't fit reader intent. |

Source of truth for thresholds is `services/scoring.py` (Python constants). `docs/playbooks/seo/04-measurement-cheatsheet.md` mirrors them for the human reader. If a threshold changes, change `scoring.py` first, then update the playbook to match.

### New schemas

```python
# output_schemas.py additions

class MetricScore(_StrictModel):
    value: float | int | str
    label: str           # GOOD | BORDERLINE | POOR
    reason: str          # one-line explanation in plain English

class QueryRow(_StrictModel):
    query: str
    impressions: int
    clicks: int
    ctr: float
    position: float

class ScoredArticlePerformance(_StrictModel):
    article_id: str
    url: str
    overall_label: str
    metrics: dict[str, MetricScore]
    top_queries: list[QueryRow]
    verdict: str

class MeasurementActionOutput(_StrictModel):
    priority: str                  # high | medium | low
    action: str                    # 1–2 sentence imperative
    affected_article_id: str       # calendar entry id, or "n/a" for net-new
    rationale: str                 # why this action, citing data

class MeasurementBriefOutput(_StrictModel):
    actions: list[MeasurementActionOutput]
    coverage_note: str
```

### Edge cases (handled in the brief, not as errors)

- Article in calendar but `status != published` → silently skipped (not measurable yet).
- Article `published` but 0 GSC rows → still listed; verdict says "no impressions in window — check indexing."
- No published articles at all → brief writes a "no measurable content yet" message and exits cleanly. Run is still successful.

### Calendar hygiene

To make `published` meaningful, a small CLI helper:

```
uv run python main.py --mark-published <article_id>
```

Sets `status: published` in `content_calendar.json` atomically (read → mutate → write). Without this, `measure` has no way to know what is live. The `published` value already exists in `ArticleStatus`; no enum change needed.

---

## 7. Wiring measurement back into the SEO agent

Closing the flywheel. Today the SEO agent reads `competitor_profiles` + `market_brief`. After this change, it *also* reads `measurement_brief.md` when present.

### Change 1 — orchestrator context injection

```python
# agents/orchestrator.py — run_weekly_batch

research_context = competitor_profiles + "\n\n" + market_brief

if file_service.MEASUREMENT_BRIEF_MD_PATH.exists():
    measurement_brief = await file_service.read_text(file_service.MEASUREMENT_BRIEF_MD_PATH)
    research_context += "\n\n" + measurement_brief
```

That is the entire orchestrator change. Graceful when the brief is missing (first run).

### Change 2 — SEO system prompt addition

New section appended to `prompts/md/agents/seo_system.md`:

```markdown
# PAST-PERFORMANCE CONTEXT (when available)

The research context may include a MEASUREMENT BRIEF section showing how previously-published articles performed. When present, use it as priority signal:

- "Recommended actions" in the brief — treat as your highest-priority candidates. If the brief says "follow-up on X" or "refresh Y", surface those before generating net-new ideas.
- High-performing articles (good position, good CTR) — propose adjacent or follow-up topics. Success is the strongest signal you have.
- "Domain-level gap opportunities" — keywords we rank for but didn't target. These are easy wins: real ranking already exists, so a properly-targeted article often jumps to page 1.
- 0-impression articles — do NOT propose retargeting the same keyword. The angle was wrong or competition was too strong. Either way, don't double down without a different angle.

If no MEASUREMENT BRIEF is in the context, proceed as before — this is normal for the first weekly batch.
```

### Change 3 — SEO agent tool list

`agents/seo_agent.py`:

```python
# before
tools = [tavily_search_tool, people_also_ask, google_trends]

# after
tools = [
    dfs_serp_live_advanced,        # replaces tavily_search for SERP
    dfs_keyword_suggestions,       # replaces pytrends for expansion
    dfs_bulk_keyword_data,         # NEW — volume + difficulty in one call
]
```

The SEO system prompt's `TOOLS` section updates to match (trivial wording change).

### Gap-opportunity continuity

For "domain-level gap opportunities" in the brief to make sense, the measurement agent reads `content_calendar.json`, builds the set of targeted keywords (primary + secondary across all entries), and computes:

```
ranked_keywords (from DFS Labs) ∖ targeted_keywords (from calendar) = gap_opportunities
```

No new tracking table — the calendar already has the data.

---

## 8. SEO playbook (the learning artifact)

Living documentation for the human operator (currently new to SEO).

**Location**: `docs/playbooks/seo/` (not under `superpowers/specs/` — these are living docs, not specs).

### Structure — 7 short docs

| File | Purpose | When to read |
|---|---|---|
| `00-overview.md` | Whole system in one diagram + 5 paragraphs. How `setup`/`weekly`/`article`/`measure` fit together and what each mode produces. | Once, then as a reference when context-switching back. |
| `01-fundamentals.md` | SEO 101 in plain English: search intent, long-tail vs head, keyword volume vs difficulty, domain authority, why low-authority sites win the long tail. No jargon without definition. | Read once front-to-back. Vocabulary unlocks everything else. |
| `02-keyword-strategy.md` | Why this system targets *informational long-tail* and avoids commercial / branded / head terms. The "weak SERP" thesis. Two worked examples (one good, one bad) using real market_brief data. | Before manually overriding the SEO agent's picks. |
| `03-dataforseo-cheatsheet.md` | What each of the 5 endpoints we call does, what its output fields mean, what they cost. How to read a SERP response. | When you see a number in the brief and aren't sure what it represents. |
| `04-measurement-cheatsheet.md` | How to read `measurement_brief.html`. What "position 12.3 with CTR 4%" actually means. Full scoring threshold table with reasoning. | Every time you open the brief, until intuitive (~3–4 weeks). |
| `05-gsc-ga4-setup.md` | One-time manual setup steps from Section 5 with screenshot placeholders. "I lost my service account JSON" recovery procedure. | Once during setup. Again when onboarding a teammate. |
| `06-when-to-refresh-vs-rewrite-vs-kill.md` | Decision tree for under-performing articles. *Refresh* (update facts, add sections) vs *rewrite* (new angle, same URL) vs *kill* (noindex + redirect). Criteria, not feelings. | When the measurement brief flags an article. |

### What gets written as part of this implementation

- All 7 files exist as committed markdown (no stubs — empty files in git are a code smell).
- `00`, `01`, `03`, `05` are **fully written** in this implementation. These are needed to operate the system on day 1.
- `02`, `04`, `06` get a **written outline + first 2–3 paragraphs each**, marked with a single `<!-- TODO: expand after first month of real data -->` comment. We need real measurement data to fill them out well; pretending otherwise produces generic content that ages badly.

### Doc-writing principles

- **Plain English.** Every term defined the first time it appears.
- **Concrete > abstract.** "CTR of 4% at position 12 is below the ~6% baseline" beats "CTR should be optimized."
- **One claim per paragraph.** No walls of text.
- **Cross-link.** Mentions of "keyword difficulty" link back to `01` for the definition.
- **Living, not finished.** Each file ends with "Last updated: YYYY-MM-DD".

### Keeping the playbook accurate

- Note in `00-overview.md`: "If you find yourself repeating an explanation to Claude in a chat, that's a signal the playbook is missing it — add it."
- `CLAUDE.md` gets a one-line addition pointing future Claude sessions at `docs/playbooks/seo/00-overview.md` as the entry point for SEO context.

### Out of scope

- Not a book on SEO (Moz / Ahrefs blog do that better).
- Not a marketing strategy doc (out of scope — this is operations, not strategy).
- Not auto-generated. Hand-written.

---

## 9. Testing, guardrails, and rollout

### Test layers

| Layer | What gets tested | How |
|---|---|---|
| Pure functions | `services/scoring.py` thresholds, calendar-gap math, brief composition helpers | Plain pytest, no mocking. |
| HTTP clients | `dataforseo_client`, `gsc_client`, `ga4_client` — auth headers, query construction, response parsing, error classification | `httpx.AsyncClient` mocked (same pattern as `test_tools.py`). Fixture JSON files in `tests/fixtures/`. |
| Cost tracker | `CostTracker` increments, cap enforcement, `DataForSEOBudgetExceeded` raised at the right boundary | Unit test. No HTTP. |
| Renderers | Given a typed `MeasurementReport`, produce expected MD/HTML | Pure transformation tests. Snapshot the output once; fail if it changes unexpectedly. |
| Measurement agent | End-to-end agent run with all three external clients mocked | Mock at the client boundary; let real aggregation run; LLM-synthesis mocked. |
| SEO agent context wiring | Brief is appended when present, omitted gracefully when not | Two cases: file exists → in context; file missing → no error, no context. |
| LLM-calling code paths | All chains and agents | Existing pattern: mock the LLM. We do not test LLM output quality (that is eval territory, separate effort). |

### Fixtures to create (in `tests/fixtures/`)

One fixture per *endpoint* (not per tool — the merged tool needs both source responses to test the merge logic):

- `dfs_serp_response.json` — Google Organic Live Advanced
- `dfs_search_volume_response.json` — Keywords Data / Search Volume
- `dfs_keyword_difficulty_response.json` — Labs / Bulk Keyword Difficulty
- `dfs_keyword_suggestions_response.json`
- `dfs_ranked_keywords_response.json`
- `gsc_search_analytics_response.json`
- `ga4_run_report_response.json`

Real (redacted) responses make tests stay honest. Synthetic responses lie.

### `--mode validate`

```
uv run python main.py --mode validate
```

Cheap checks against every external integration without calling expensive endpoints:

- **DataForSEO**: `/appendix/user_data` (free, returns account info, confirms auth)
- **GSC**: `sites.list()` (free, lists properties the service account can see — confirms permission granted)
- **GA4**: list-properties via Admin API (free, confirms property ID + permission)

Outputs a pass/fail report per integration. Run immediately after the manual setup steps in Section 5, before running `measure` for real. Catches ~90% of setup mistakes in 5 seconds for $0.

### Guardrails (recap)

1. `MAX_COST_PER_RUN = $1.00` in `dataforseo_client.py`. Hard cap. Raises `DataForSEOBudgetExceeded`. Configurable via env var only — no CLI flag, intentional friction.
2. `MAX_CALLS_PER_RUN = 50` — also in `dataforseo_client.py`. Catches runaway loops before they hit the cost cap.
3. **No `published` → no measurement.** Articles must be marked `published` via `--mark-published <id>` to enter the brief.
4. **Measurement is read-only outside the repo.** `measure` never POSTs/PUTs to GSC, GA4, or DataForSEO. The only writes are `data/measurement_brief.{md,html}` locally.
5. **No secrets in repo.** Service account JSON lives at `~/.config/draftandarc/gcp-service-account.json` (outside the project). `.gitignore` already covers `.env`. Adds the JSON path defensively even though it is outside the tree.
6. **Atomic calendar updates.** `--mark-published` reads → mutates → writes back atomically — same pattern as existing `update_status`.

### Rollout sequence

Ordered so each piece is independently shippable and revertable:

1. `services/dataforseo_client.py` + `tools/dataforseo.py` (no agent changes yet — tools exist but unused).
2. Add `--mode validate` for DataForSEO. Verify auth works end to end.
3. Swap SEO agent tool list (Tavily-SERP → DFS-SERP, etc.). Run a real weekly batch; compare output to the last manual one. **Decision point: continue or revert.**
4. `services/gsc_client.py` + `services/ga4_client.py` + `--mode validate` extended.
5. `services/scoring.py` + renderers.
6. `agents/measurement_agent.py` + `--mode measure` + `--mark-published`.
7. Wire measurement brief into orchestrator (SEO agent reads it).
8. Playbook docs.

After step 3, the SEO agent is already better. After step 7, the loop is closed. Each step is a small PR or commit.

---

## 10. Known limitations and open questions

### Known limitations (called out so they are not surprises)

- **Thin signal for 30–60 days post-launch.** `measurement_brief.md` will be mostly empty stubs until Google indexes and ranks the content. The integration is correct from day 1; the *signal* is thin until you have real impressions. Playbook calls this out explicitly so the operator does not conclude something is broken when it is just early.
- **`signup_cta_click` event not yet emitted by the blog template.** Engagement data is available immediately; conversion data requires a one-line `gtag` addition on the blog page. Flagged for follow-up; out of scope for this spec.
- **No Medium-side stats.** If you republish articles to Medium with canonical-to-self URLs, Medium will have its own internal stats this system does not read. Acceptable — canonical points authority to your domain, which is where measurement happens.

### Open questions for the operator to decide before implementation

None blocking. All foundational decisions are locked in Section 2.

### Decisions deliberately deferred to future specs

- Article-quality improvements (writing prompt upgrades, programming-specific patterns).
- Generation of the 10-article batch (5 on-demand topic-teasers + 5 standard with programming focus).
- Automated article-refresh workflow.
- Conversion event implementation on the blog template.
- Second SEO data provider for redundancy.

---

## 11. Summary

This spec adds a measurement spine to the existing marketing-agent system. It replaces SerpAPI and pytrends with DataForSEO (richer SEO data on the input side), adds GSC and GA4 integrations (real performance data on the output side), introduces a new `--mode measure` that produces a dual-output brief (markdown for the SEO agent, HTML dashboard for the human), and wires that brief back into the next weekly batch so the agent's choices are informed by past performance.

The change is intentionally minimal: ~15 files added, ~10 changed, no rewrites. Each piece is independently shippable. A hand-written playbook turns the integration into something the operator can actually learn from, not just operate.

Total ongoing cost: approximately $0.10 per week against a $50 DataForSEO budget. Total implementation surface: small enough to ship in a single focused session per rollout step.

The leverage is high because measurement turns every future decision in this system from guess to evidence.
