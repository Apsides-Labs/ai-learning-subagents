# SEO Fundamentals

A 10-minute read that defines the vocabulary every other doc in this folder assumes you know.

## Search intent

What the person searching actually wants. The same words can mean different things:

- **Informational**: "what is the feynman technique" — they want to *learn*.
- **Commercial**: "best feynman technique app" — they want to *compare options before buying*.
- **Transactional**: "feynman technique app download" — they're ready to *act*.
- **Navigational**: "draft and arc login" — they want a *specific site*.

This system targets **informational** intent. That's where a new domain with low authority can win — the SERPs are less competitive and the content can be genuinely useful without being a sales pitch.

## Volume

"How many people search this per month, on average?" Reported by DataForSEO (`search_volume` field) and Google Ads.

- Under 50: long-tail. Genuine demand, but a single article on its own won't move traffic.
- 50–500: sweet spot for a low-authority domain. Real readers, reachable competition.
- 500–5,000: meaningful traffic if you rank, but you'll usually need either authority or a much better angle than the existing top-10.
- 5,000+: head terms. Out of reach for new domains until you have backlinks and history.

## Difficulty

"How hard is it to rank in the top 10 for this query?" 0–100 score from DataForSEO. Higher = harder.

- 0–20: a well-targeted article from a new domain has a realistic shot.
- 20–35: borderline. Worth it if the SERP is weak (see "weak SERP" below).
- 35+: avoid for now.

## Long-tail vs. head

- **Head term**: short, broad. "learn python".
- **Long-tail**: longer, more specific. "how to learn python decorators in one weekend".

Long-tail keywords have lower volume but also lower difficulty. They convert better because the searcher's intent is clearer. A site with no authority should target long-tail almost exclusively until it has earned some.

## Position

Where your URL ranks in Google's results, averaged across impressions.

- Position 1–3: top of page 1. Real traffic — 50%+ of all clicks for that query go here.
- Position 4–10: rest of page 1. Some traffic, but the top 3 take most of it.
- Position 11–20: page 2. Effectively zero clicks. People rarely scroll past page 1.
- Position 21+: not worth optimizing for; treat as "not ranking".

## CTR (Click-Through Rate)

Clicks ÷ impressions. The "is the title compelling?" metric. There's an expected CTR at each position (roughly: pos 1 ≈ 28%, pos 3 ≈ 11%, pos 10 ≈ 3%). If your CTR is well below expected, the article *could* rank but the title isn't earning the click. Title rewrite is usually the fix.

## Domain authority

Google's general trust in your site. New domains start at zero and earn authority by being linked to from other reputable sites, accumulating organic traffic, and producing consistent quality content. This system can't fake authority — but a low-authority site can still win the long-tail by writing better content for underserved searches.

## Weak SERP

The single most important concept in this whole playbook.

A SERP is "weak" when the top 10 results don't actually answer the searcher's question well. Signs of a weak SERP:

- Top results are old (2021 or earlier on a topic that has evolved).
- Top results are thin (300-word listicles, generic recommendations).
- Top results pattern-match the keyword but miss the searcher's real need.
- The top 10 includes scrappy Medium posts, Reddit threads, or small-blog content — not Wikipedia/Coursera/edX dominance.

Weak SERPs are where new domains win. When the SEO agent picks a keyword, it's looking for: low difficulty + weak SERP + clear informational intent. That combination is the highest-leverage decision the system makes each week.

## What this system optimizes against

- **Long-tail informational keywords** (3+ words, "how to / why / what is" shapes)
- **Weak SERPs** (top 10 has reachable competitors and thin content)
- **Difficulty under 30**
- **Search volume between 50 and 1,000**

Anything outside this band is deliberately ignored. The playbook in `02-keyword-strategy.md` explains why.

---
Last updated: 2026-05-26
