# SEO System Overview

This is the entry point for understanding what the marketing-agent system does, how the four modes fit together, and where to read next.

## The flywheel

```
setup  →  weekly  →  article  →  publish  →  measure
                                                  │
                                                  └─ feeds into next weekly's SEO agent
```

| Mode | What it does | When to run |
|---|---|---|
| `setup` | Reads the product codebase and competitor pages. Writes `product_facts.md` and `competitor_profiles.md`. | Once. Re-run when the product or competitor set changes meaningfully. |
| `weekly` | Refreshes market data (pain points, opportunities) → asks the SEO agent to pick 4 new article ideas → adds them to `content_calendar.json` as `planned`. | Once a week. |
| `article` | Writes one draft from the next `planned` entry. Fact-checks against product facts. Opens a PR to the blog repo. | After `weekly`, once per article you want to ship that week. |
| `measure` | Pulls Google Search Console + GA4 + DataForSEO ranked-keywords. Produces `data/measurement_brief.{md,html}`. The MD feeds back into next `weekly`'s SEO context. | Weekly, ideally a few days after publishing so Google has time to index. |

## The two new external tools

- **DataForSEO** (`services/dataforseo_client.py`): replaces the previous SerpAPI + pytrends combo. Single API for SERP, keyword volume, difficulty, and domain-level ranked keywords. ~$0.10–0.30/week at current usage.
- **Google Search Console** (`services/gsc_client.py`) + **GA4** (`services/ga4_client.py`): the feedback loop. Tell us which queries surface our articles, at what position, with what CTR, and what people do on the page once they arrive.

## What to read next

- New to SEO? → `01-fundamentals.md`
- Setting up GSC/GA4 for the first time? → `05-gsc-ga4-setup.md`
- Want to understand what's in a measurement brief? → `04-measurement-cheatsheet.md`
- Curious what DataForSEO charges for? → `03-dataforseo-cheatsheet.md`
- An article is underperforming and you don't know what to do? → `06-when-to-refresh-vs-rewrite-vs-kill.md`

## Keeping this playbook accurate

If you find yourself repeating an explanation to Claude in a chat, that's a signal the playbook is missing it — add it. These docs are living, not finished.

---
Last updated: 2026-05-26
