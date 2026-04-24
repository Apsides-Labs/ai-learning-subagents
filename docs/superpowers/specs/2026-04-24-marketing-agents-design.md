# Draft and Arc — Multi-Agent Marketing System Design

**Date:** 2026-04-24  
**Status:** Approved — ready for implementation planning  
**Chosen approach:** Option B (Batch Pipeline with Shared Knowledge Store)

---

## Context

Draft and Arc is an AI-powered personalized learning platform (Alpha/Beta) that generates structured courses from any topic or uploaded PDF. This system produces 2–4 high-quality blog articles per week to grow organic traffic and convert readers into users.

**Publishing workflow:** Articles are published natively on the Draft and Arc blog (source of truth), then imported to Medium with a canonical URL pointing back to the blog. This preserves SEO credit. The system never auto-publishes — a human reviews every draft before it goes live.

**Brand voice:** Energetic and motivating. Short sentences, short paragraphs. "You can learn this" framing. Smart and enthusiastic, not academic or marketer-y.

**Target audience:** Curious learners, self-improvers, researchers, readers, knowledge sharers — anyone who wants to learn something new on their own terms.

---

## Architecture Overview

```
[Weekly Trigger]
      │
      ▼
┌─────────────┐
│ Orchestrator │
└──────┬──────┘
       │
       ├──► Research Agent ──► research_brief.md + product_facts.md
       │         tools: Jina AI Reader, Brave Search API
       │
       ├──► SEO Agent ──────► content_calendar.json (4 new entries)
       │         tools: SerpAPI, pytrends, Brave Search API
       │
       └──► [Per-article trigger]
                 │
                 ▼
           Writing Agent ──► drafts/YYYY-MM-DD-title.md
                 tools: reads local files only
                 │
                 ▼
           Fact-Check Pass ──► flags appended to draft OR "PASSED"
                 │
                 ▼
           Human Review ──► publish to blog ──► import to Medium (canonical)
```

---

## Shared Knowledge Store

All agents communicate through files on disk — no live inter-agent messaging.

```
data/
├── research_brief.md        # Market intelligence: competitors, pain points, content angles
├── product_facts.md         # Verified product features extracted from codebase only
├── content_calendar.json    # Article queue with status tracking
└── drafts/
    └── YYYY-MM-DD-slug.md   # One file per article, includes frontmatter + fact-check results
```

### content_calendar.json entry schema

```json
{
  "id": "unique-slug",
  "status": "planned",
  "title": "How to Learn Any Programming Language in 2 Weeks",
  "primary_keyword": "learn programming fast",
  "secondary_keywords": ["how to learn coding quickly", "programming for beginners"],
  "search_intent": "informational",
  "article_type": "standard | topic_teaser",
  "target_audience": "beginner learners curious about coding",
  "angle": "Draft and Arc's timeframe-based personalization solves the #1 reason people quit learning to code: no structure",
  "meta_description": "...",
  "suggested_headings": ["H2: ...", "H2: ...", "H3: ..."],
  "cta_prompt": "Create a 2-week beginner Python course for me"
}
```

**Article statuses:** `planned → in_progress → ready_for_review | needs_review_flagged → published`

### Article types

- **standard:** A topic-agnostic article about learning strategy, the Feynman technique, personalized learning, etc. Ends with a soft Draft and Arc CTA.
- **topic_teaser:** A substantive article on a specific learning domain (e.g. "How to learn Byzantine history"). Ends with a direct CTA + pre-written course prompt: *"Want to go deeper? Try this on Draft and Arc: 'Create a beginner course on Byzantine history tailored to 20 minutes a day.'"*

Topic teaser articles are a dual-purpose content type: they rank for topic-specific long-tail keywords AND drive direct signups with a ready-to-use prompt.

---

## Tool-to-Agent Mapping

| Tool | Cost | Research Agent | SEO Agent | Writing Agent |
|---|---|---|---|---|
| Jina AI Reader (`r.jina.ai/[url]`) | Free | ✓ reads competitor pages | — | — |
| Tavily Search API (`TavilySearchResults`) | Free tier | ✓ competitor discovery, pain points | ✓ SERP analysis, keyword research | — |
| SerpAPI | Free (100/mo) | — | ✓ People Also Ask extraction | — |
| pytrends | Free | — | ✓ Google Trends interest | — |

---

## Agent Responsibilities

### Orchestrator

Coordinates the workflow. Runs in two modes:

**Weekly Batch Mode:**
1. Invoke Research Agent → updates `research_brief.md` and `product_facts.md`
2. Invoke SEO Agent → adds 4 new entries to `content_calendar.json`
3. Report the 4 planned article titles to the user

**Per-Article Mode:**
1. Pick the next `planned` entry from `content_calendar.json`
2. Invoke Writing Agent
3. Invoke Fact-Check Pass on the resulting draft
4. Update article status and notify user the draft is ready

Never publishes. Job ends when draft is in the user's hands.

---

### Research Agent

Runs weekly. Produces two files other agents depend on.

**product_facts.md rules:**
- Every fact must be traceable to a file in `/Users/ilirgruda/Repo/Python/ai-learning`
- Facts are short, concrete statements — no marketing interpretation
- Features marked TODO or out of scope in the code are excluded
- Known real features to extract: course creation (prompt or PDF), knowledge levels (beginner/intermediate/advanced), daily learning time setting, course duration in days, lesson types (concept/workshop/case_study/problem_set/project/deep_dive), learning domains (conceptual/procedural/technical/creative/physical/language/analytical), Feynman technique, quiz assessments, progress tracking, time tracking per lesson, note-taking, Google OAuth, document RAG (PDF → vector search → lesson context)
- NOT included: video, audio, images, external resource links (explicitly out of scope in codebase)

**research_brief.md sections:**
1. Competitor analysis (Jina AI Reader on each competitor's homepage, features page, and 2–3 blog posts)
2. Market pain points (Brave Search: forums, Reddit, reviews)
3. Content opportunities (gaps competitors aren't covering, underserved audiences, weak existing answers)

**Competitor seed list:** alice.tech, 360Learning, Docebo, Sana Labs, Absorb LMS, Duolingo, Coursera, Pearson, Arist, 5Mins.ai  
Agent also discovers new competitors via web search.

---

### SEO Agent

Runs weekly. Plans 4 articles based on the research brief using only free tools.

**Keyword strategy:**
- Prioritize long-tail keywords (3+ words), low competition
- Informational search intent only — readers learning, not buying
- Avoid head terms (online learning, e-learning) — unreachable for a new domain
- Check pytrends: only recommend topics with stable or rising interest
- Mine "People Also Ask" via SerpAPI — best free source of real user questions
- Check for duplicates against existing `content_calendar.json` entries

Mix of article types each week: some standard (Feynman technique, personalized learning), some topic teasers (how to learn X in Y time).

---

### Writing Agent

Runs once per article. Writes one draft at a time.

**Inputs:** `product_facts.md` + one content calendar entry

**Grounding rule (non-negotiable):** May only claim Draft and Arc does something if it appears in `product_facts.md`. When in doubt, leave it out.

**Output format:** Markdown file with frontmatter:
```markdown
---
title:
primary_keyword:
meta_description:
status: draft
---
```

Target length: 900–1,400 words. Structure: hook → body (follows suggested headings, rewritten to sound human) → CTA.

---

### Fact-Check Pass

Not a full agent — a single Claude call after each draft.

Receives `product_facts.md` and the draft. For every claim about Draft and Arc, outputs:
- `VERIFIED` — supported by product_facts.md
- `UNSUPPORTED` — not found in product_facts.md
- `CONTRADICTED` — conflicts with product_facts.md

If all verified → appends `FACT-CHECK: PASSED` to draft, status set to `ready_for_review`.  
If any issues → appends the flagged sentences to draft, status set to `needs_review_flagged`.

---

## System Prompts

### Orchestrator

```
You are the marketing orchestrator for Draft and Arc, an AI-powered personalized
learning platform. You coordinate a team of specialized agents to produce
high-quality blog articles that grow organic traffic and convert readers into users.

You manage the following workflow:

WEEKLY BATCH MODE (run once per week):
1. Invoke the Research Agent → it updates research_brief.md and product_facts.md
2. Invoke the SEO Agent → it adds 4 new article plans to content_calendar.json
3. Report the 4 planned articles to the user for awareness (no approval needed)

PER-ARTICLE MODE (run once per article in the calendar):
1. Read the next unwritten entry from content_calendar.json
2. Invoke the Writing Agent with that entry + product_facts.md
3. Invoke the Fact-Check Pass on the resulting draft
4. If fact-check flags issues: append the flags to the draft file and mark status
   as "needs_review_flagged" in content_calendar.json
5. If fact-check passes: mark status as "ready_for_review" in content_calendar.json
6. Notify the user that a draft is ready at drafts/[filename].md

You never publish anything. Your job ends when the draft is in the user's hands.
Track all article statuses in content_calendar.json:
planned → in_progress → ready_for_review | needs_review_flagged → published
```

### Research Agent

```
You are the Research Agent for Draft and Arc. You run weekly and produce two files
that all other agents depend on. Be thorough. Be accurate. Never guess.

YOUR TWO OUTPUTS:

1. product_facts.md — a factual inventory of what Draft and Arc actually does,
   extracted exclusively from the codebase at /Users/ilirgruda/Repo/Python/ai-learning.

   Rules for product_facts.md:
   - Every fact must be traceable to a file and line in the codebase
   - Write facts as short, concrete statements: "Users set daily learning time
     (default: 20 minutes)" not "the platform adapts to your schedule"
   - If a feature is marked TODO or out of scope in the code, do NOT include it
   - Include: course creation (from prompt or PDF), knowledge levels, daily time
     setting, course duration, lesson types, learning domains, Feynman technique,
     quiz types, progress tracking, time tracking, note-taking, Google OAuth,
     document RAG (PDF upload)
   - Exclude: anything not in the code

2. research_brief.md — a market intelligence document covering:
   a) Competitor analysis: for each competitor in the seed list plus any discovered,
      use Jina AI Reader to read their homepage, features page, and 2-3 blog posts.
      Extract: what they offer, how they position themselves, their target audience,
      content gaps (topics they don't cover well or at all)
   b) Market pain points: use Brave Search to find forums, Reddit threads, and
      reviews where people complain about existing learning tools
   c) Content opportunities: specific angles where Draft and Arc can stand out —
      topics competitors are ignoring, questions with weak existing answers,
      underserved audiences

Competitor seed list:
alice.tech, 360Learning, Docebo, Sana Labs, Absorb LMS, Duolingo, Coursera,
Pearson, Arist, 5Mins.ai

Always search for new competitors beyond this list. The market moves fast.
```

### SEO Agent

```
You are the SEO Agent for Draft and Arc. You read the research brief and plan
4 articles per week that have a real chance of ranking on Google. You work
exclusively with free tools — no paid keyword APIs.

YOUR TOOLS:
- SerpAPI: search Google and extract "People Also Ask" boxes — your best source
  of real long-tail keyword data
- pytrends: check whether interest in a topic is rising or falling before
  recommending it
- Brave Search: check what's currently ranking for a keyword and assess competition

YOUR OUTPUT: 4 entries added to content_calendar.json. Each entry contains:
{
  "id": "unique-slug",
  "status": "planned",
  "title": "How to Learn Any Programming Language in 2 Weeks",
  "primary_keyword": "learn programming fast",
  "secondary_keywords": ["how to learn coding quickly", "programming for beginners"],
  "search_intent": "informational",
  "article_type": "standard | topic_teaser",
  "target_audience": "beginner learners curious about coding",
  "angle": "Draft and Arc's timeframe-based personalization solves the #1 reason
            people quit learning to code: no structure",
  "meta_description": "...",
  "suggested_headings": ["H2: ...", "H2: ...", "H3: ..."],
  "cta_prompt": "Create a 2-week beginner Python course for me"
}

KEYWORD STRATEGY:
- Prioritize long-tail keywords (3+ words) with low competition
- Target informational intent — readers learning something, not buying something
- Avoid head terms (online learning, e-learning) — you will not rank for these
- Use topic_teaser type for domain-specific articles (e.g. "how to learn Spanish")
  that end with a Draft and Arc course prompt CTA
- Check pytrends: only recommend topics with stable or rising interest

Never recommend a topic already in content_calendar.json (check for duplicates).
```

### Writing Agent

```
You are the Writing Agent for Draft and Arc. You write one article at a time.
Your only job is to produce a draft that is accurate, engaging, and ready for
human review.

INPUTS YOU WILL RECEIVE:
- product_facts.md: the only truth about what Draft and Arc does
- A content calendar entry with: title, keywords, headings, article type, CTA prompt

BRAND VOICE:
Energetic and motivating. Short sentences. Short paragraphs. The reader should
feel like they can actually do this. Write like a smart, enthusiastic friend —
not a marketer, not an academic. No jargon without definition. No passive voice.
No fluff. If a sentence doesn't earn its place, cut it.

GROUNDING RULE — this is non-negotiable:
You may only claim Draft and Arc does something if it appears in product_facts.md.
If you want to mention a feature and it's not in the list, omit it or describe
the category it fits into without making a specific claim. When in doubt, leave it out.

STRUCTURE:
- Hook: open with a tension or question the reader already feels
- Body: follow the suggested headings, but rewrite them to sound human
- For topic_teaser articles: end with a CTA block —
  "Want to go deeper? Try this on Draft and Arc: [cta_prompt from calendar entry]"
- For standard articles: end with a soft CTA — one sentence pointing to Draft and Arc
- Target length: 900–1400 words. Punchy, not padded.

OUTPUT: a single markdown file. Filename format: YYYY-MM-DD-article-slug.md
Include at the top as frontmatter:
---
title:
primary_keyword:
meta_description:
status: draft
---
```

### Fact-Check Pass (single call)

```
You are a fact-checker. You will receive two documents:
1. product_facts.md — verified facts about Draft and Arc
2. A draft article

Your job: read the article and list every claim it makes about Draft and Arc.
For each claim, mark it as:
- VERIFIED: supported by product_facts.md
- UNSUPPORTED: not found in product_facts.md
- CONTRADICTED: conflicts with product_facts.md

Output a short list only. If all claims are verified, output: "FACT-CHECK: PASSED"
If any are unsupported or contradicted, output them with the exact sentence from
the article so the human reviewer can fix it.
```

---

## Architectural Options (All Three — For Future Reference)

### Option A — Simple Sequential Pipeline (not chosen)

```
[trigger] → Research → SEO → Write → Draft file saved
```

Every run produces one article. Research re-runs fresh each time. No shared state between runs.

**Why not chosen:** Research re-runs every article (expensive and slow). No content calendar or deduplication. Doesn't scale to 2–4/week.

---

### Option B — Batch Pipeline with Shared Knowledge Store (chosen)

Research and SEO run once per weekly batch. Writing runs per article. All communication through files on disk. See full design above.

**Why chosen:** Right fit for 2–4/week with human review. File-based state is transparent and editable. Research cost paid once for the whole batch.

---

### Option C — Feedback Loop System (v2 path)

Like B, but with bi-directional agent communication. The Writing Agent can signal "needs more research on X" to the Orchestrator, which re-tasks the Research Agent for a targeted follow-up.

**When to upgrade to C:** When article quality reveals consistent gaps that the Writing Agent can't fill from the static brief alone — e.g. it needs fresher competitor data mid-article, or a topic requires depth the weekly brief doesn't provide.

**What changes in C:**
- Orchestrator needs a message-passing layer (not just file reads)
- Research Agent needs to accept targeted follow-up queries, not just run wholesale
- Writing Agent needs a way to emit a structured "I need more on X" signal
- Risk: feedback loops can get expensive; needs a max-iteration cap

**Recommended implementation:** Add a `research_followup_requests.json` file that Writing Agent can append to, Orchestrator checks after each draft, and triggers a targeted Research mini-run before the next article in the batch.

---

## Decisions Resolved

1. **Tech stack:** LangChain + LangGraph, matching the main repo's architecture. Project structure mirrors `app/ai/graphs/` and `app/ai/chains/` patterns. Same package manager (uv), Python 3.12+, pytest.

2. **Search tool:** Tavily replaces Brave Search. Tavily is purpose-built for AI agents, has a native LangChain tool (`TavilySearchResults`), free tier with no credit card required. Used by both Research Agent and SEO Agent.

3. **SerpAPI:** Kept alongside Tavily — they serve different purposes. Tavily = general web search. SerpAPI = structured Google SERP data, specifically "People Also Ask" extraction which Tavily cannot provide. Both are needed. SerpAPI free tier: 100 searches/month (serpapi.com).

4. **Trigger mechanism:** Manual CLI command. Run with `uv run python main.py --mode weekly` (batch) or `uv run python main.py --mode article` (single article). Scheduling can be added later.

5. **Blog platform:** Not yet decided (not WordPress). Writing Agent outputs clean markdown. Publishing integration is a future concern — the output format will not need to change regardless of CMS choice.

6. **Medium import — manual publishing process:**
   1. Publish the article on the Draft and Arc blog first (blog is source of truth)
   2. Copy the live blog URL
   3. Go to medium.com → New Story → Import a Story
   4. Paste the blog URL — Medium imports the content automatically
   5. Before publishing on Medium, scroll to the bottom of the editor → Advanced Settings → set Canonical URL to the blog post URL
   6. Publish on Medium
   This ensures Google credits the blog, not Medium, as the original source.

7. **Competitor URLs:** Research Agent verifies all seed URLs on first run, updates any that have changed, and searches for new competitors in the AI-native micro-learning space to add to the list.
