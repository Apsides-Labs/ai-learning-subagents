# Measurement Cheatsheet

How to read `data/measurement_brief.html` after running `--mode measure`. The full scoring threshold table is below.

## What's in the HTML brief

Six sections, top to bottom:

1. **Glossary** — definitions of every metric. Re-read whenever a term feels fuzzy.
2. **Headline** — total impressions, clicks, CTR, avg position across all published blog content in the window.
3. **Per-article performance** — one card per article. Colored badges show GOOD / BORDERLINE / POOR for each metric, plus an overall label.
4. **Domain-level gap opportunities** — keywords your domain ranks for that you didn't target. Usually the easiest follow-up content.
5. **Recommended actions** — LLM-synthesized to-do list, ranked by priority. HIGH actions warrant doing this cycle; LOW actions are nice-to-haves.
6. **Coverage note** — any data-source failures, early-data caveats, or other context.

The MD brief (`data/measurement_brief.md`) is the same data without glossary or badges — it's for the next weekly batch's SEO agent.

## The scoring thresholds

These are source-of-truth in `services/scoring.py`; this table mirrors them.

| Metric | GOOD | BORDERLINE | POOR | INSUFFICIENT_DATA |
|---|---|---|---|---|
| Avg position | 1.0–3.5 | 3.5–10.5 | 10.5+ | (n/a) |
| CTR | matches expected for position | within 50% of expected | <50% of expected | (n/a) |
| Impressions | 100+ in 28d | 10–99 | <10 after 14 days | <14 days post-publish |
| Engagement time | 2:00+ | 0:30–2:00 | <0:30 | (n/a) |
| CTA click rate | 2%+ | 0.5–2% | <0.5% | <10 users |

### Why these thresholds

<!-- TODO: expand after first month of real data — calibrate with your actual baseline -->

- **Position**: at positions 1–3 you get real clicks; 4–10 gets ~10–20% of the clicks the top 3 do; 11+ is effectively zero clicks.
- **CTR**: at any given position there's an expected CTR. If yours is much lower, the title isn't earning the click.
- **Impressions <14 days**: too early to judge. Google needs ~2 weeks to fully index, rank, and accumulate impressions on a new article.
- **Engagement time <30s**: bounce before reading. The headline pulled them in, the article lost them.
- **CTA rate <10 users**: too small a sample. Don't make decisions on it.

## What to do for each label

<!-- TODO: expand to a full decision tree once we have real data — the placeholder below is directionally right but needs refinement -->

- **All metrics GOOD**: write a follow-up article on an adjacent topic. Success compounds.
- **Position GOOD, CTR POOR**: title/meta-description rewrite. Don't touch the body.
- **Position BORDERLINE**: content refresh — add depth, examples, recency. Same URL.
- **Position POOR + 30+ days**: see `06-when-to-refresh-vs-rewrite-vs-kill.md`.
- **0 impressions after 14+ days**: indexing problem, not a quality problem. Check GSC URL Inspection.

## What to ignore on a new site

For the first 30–60 days, almost everything will be `INSUFFICIENT_DATA`. That's normal. The system is correctly identifying that there isn't enough signal to judge yet. Don't take action on under-14-day articles based on the brief; trust that the indexing process is normal.

---
Last updated: 2026-05-26
