# Keyword Strategy

How this system decides which keywords to target — and why those are not the keywords most "SEO experts" would name.

## The thesis

Draft and Arc is a new domain. We cannot win head terms ("learn programming", "study tips") against Wikipedia, Coursera, or Khan Academy. But we can win specific, underserved searches where the existing top 10 is genuinely weak. Long-tail informational keywords + weak SERPs = the entire opportunity space.

## The four filters

The SEO agent applies all four to every candidate:

1. **3+ word query** — specificity correlates with reachability.
2. **Informational intent** — no "best", "vs", "alternative", "pricing", "free download".
3. **Difficulty under 30** (DataForSEO `keyword_difficulty`).
4. **Volume between 50 and ~1,000** — large enough to matter, small enough to be reachable.

Tiebreak: among survivors, prefer SERPs where the top 10 is weak (outdated, thin, pattern-matching the keyword without answering the question).

## Worked example: a winning candidate

<!-- TODO: expand after first month of real data — use actual market_brief.md entries + their DataForSEO scores -->

The shape we're looking for:

- Keyword: `how to get rid of tutorial hell`
- Volume: 260 (small, but real)
- Difficulty: 19 (low)
- SERP: Reddit threads + a few Medium posts in the top 10, no Wikipedia or Coursera presence
- Intent: clearly informational — they're stuck, they want a process

This is "win-able". A focused 1,200-word article with a concrete how-to has a realistic shot at the top 5.

## Worked example: a candidate to drop

<!-- TODO: expand after first month of real data -->

The shape we're avoiding:

- Keyword: `best learning apps 2026`
- Volume: 8,100 (high)
- Difficulty: 67 (high)
- SERP: PCMag, Wirecutter, Forbes, NYT Wirecutter
- Intent: commercial — they're shopping

Even if we could rank, the intent is wrong: this searcher wants a list to choose from, not our story.

## When to manually override

The SEO agent is right ~80% of the time. The 20% of cases worth overriding:

- The agent picked a keyword whose intent is subtler than the surface words suggest.
- The agent missed a follow-up opportunity from a high-performing article in the measurement brief.
- A timely event (product launch, news story) makes a normally-bad keyword temporarily worth it.

Override by editing `content_calendar.json` directly before running `--mode article`. Don't run `--mode weekly` again — that adds 4 *more* entries.

---
Last updated: 2026-05-26
