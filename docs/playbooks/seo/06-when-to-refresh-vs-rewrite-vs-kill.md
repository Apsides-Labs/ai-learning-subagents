# When to Refresh, Rewrite, or Kill an Article

A decision tree for articles flagged by the measurement brief. Three options, three different costs.

## The three actions

| Action | What it means | Cost | When |
|---|---|---|---|
| **Refresh** | Update facts, add depth, freshen examples. Keep the angle and URL. | ~1 hour | Article is ranking but slipping; SERP has gotten more competitive. |
| **Rewrite** | New angle, same URL. The structure and thesis change; the URL doesn't. | ~3 hours | Article ranks for the keyword you targeted but the *intent* you assumed turned out wrong, OR CTR is poor at a decent position. |
| **Kill** | `noindex` it, redirect to a related article (or the blog index). The URL disappears from Google. | ~10 minutes | Article has 0 impressions after 60+ days OR ranks for nothing useful AND the angle has no salvageable framing. |

## The decision tree

<!-- TODO: expand after first month of real data — current tree is directional, refine as we learn -->

```
Did the brief flag this article?
├── Position is GOOD, CTR is POOR
│   └── REWRITE the title and meta description only. Don't touch the body.
│
├── Position is BORDERLINE (4-10)
│   ├── Article is <90 days old
│   │   └── REFRESH: add 1-2 new sections, update any dated examples.
│   └── Article is >90 days old AND no improvement after refresh
│       └── REWRITE with a sharper angle.
│
├── Position is POOR (11+)
│   ├── 0 impressions, <60 days
│   │   └── Check GSC URL Inspection for indexing issues FIRST. Don't rewrite blind.
│   ├── 0 impressions, 60+ days
│   │   └── KILL.
│   └── Has some impressions but POOR position
│       └── REWRITE with a different angle (the current one isn't earning its place).
│
└── Engagement is POOR but position/CTR fine
    └── REFRESH the article body — they're clicking but bouncing.
```

## How to actually kill an article

1. Set `status: shelved` on the calendar entry (don't delete it — keep the planning history).
2. In the blog repo, add `<meta name="robots" content="noindex">` to the article's frontmatter (or remove the article and add a 301 redirect to a related article via the blog template's redirect map).
3. Open a PR. Once merged and Google re-crawls (~1-2 weeks), the URL disappears from results.

## Don't do these things

- Don't make refresh-vs-rewrite decisions on articles less than 30 days old. The data isn't stable enough.
- Don't kill an article over one bad weekly brief. Look at 2-3 cycles.
- Don't refresh an article more than 3 times. If the angle isn't working, rewrite.

---
Last updated: 2026-05-26
