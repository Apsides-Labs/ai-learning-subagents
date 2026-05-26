# DataForSEO Cheatsheet

What each endpoint we call does, what its output fields mean, and what it costs.

See `01-fundamentals.md` for definitions of volume, difficulty, position, CTR.

## The five endpoints we use

### 1. SERP / Google / Organic / Live Advanced

**What:** Real Google SERP for one query. Returns top 10 organic + People Also Ask + related searches in one call.

**Cost:** ~$0.002 per query.

**Called from:** the SEO agent's `dfs_serp_live_advanced` tool, on shortlisted candidates.

**Key output fields:**
- `items[].type == "organic"`: a normal search result. Has `rank_absolute` (position), `domain`, `title`, `description`, `url`.
- `items[].type == "people_also_ask_element"`: the PAA box. Has nested `items` with `title` (the question).
- `items[].type == "related_searches_element"`: Google's related-search suggestions.

**When you'd read it yourself:** sanity-checking a candidate keyword. If the top 5 results are all from coursera.org / khanacademy.org / wikipedia.org, the SERP is "unreachable" and the agent should drop it.

### 2. Keywords Data / Google Ads / Search Volume

**What:** Real monthly search volume + competition + CPC, bulk (up to 1000 keywords per call).

**Cost:** ~$0.05 per 1000 keywords.

**Called from:** `dfs_bulk_keyword_data` tool (merged with difficulty endpoint).

**Key output fields:**
- `search_volume`: rough monthly average. Treat as a magnitude indicator, not a precise number.
- `competition`: 0–1 score for *advertiser* competition. Not the same as SEO difficulty. Higher means more advertisers bid on the term.
- `cpc`: cost-per-click for advertisers. High CPC often correlates with commercial intent — useful warning sign.

### 3. Labs / Google / Bulk Keyword Difficulty

**What:** 0–100 difficulty score per keyword. Higher = harder to rank.

**Cost:** ~$0.01 per 1000 keywords (verify against the dashboard — pricing has historically been less clear-cut for Labs).

**Called from:** `dfs_bulk_keyword_data` tool, alongside Search Volume.

**Key output fields:**
- `keyword_difficulty`: integer 0–100. Under 30 = reachable from a new domain.

### 4. Labs / Google / Keyword Suggestions

**What:** Long-tail variants for a seed keyword, with volume + difficulty.

**Cost:** ~$0.01 per task.

**Called from:** `dfs_keyword_suggestions` tool, once per content opportunity.

**Key output fields:**
- `items[].keyword`: the variant.
- `items[].search_volume`, `items[].keyword_difficulty`: same meaning as above.

### 5. Labs / Google / Ranked Keywords for Domain

**What:** Every keyword our domain currently ranks for (any position).

**Cost:** ~$0.02 per task.

**Called from:** the measurement agent. **Not** exposed to the SEO agent — see spec Section 4 endnote on why.

**Key output fields:**
- `items[].keyword_data.keyword`: the keyword we rank for.
- `items[].ranked_serp_element.rank_absolute`: our position.
- `items[].ranked_serp_element.url`: which of our URLs ranks.

The measurement agent filters this list down to `/blog/` URLs and diffs against the keywords we *targeted* (from `content_calendar.json`). The difference is the "gap opportunities" list — keywords we accidentally rank for that we didn't try to rank for. Often the easiest follow-up content.

## How to monitor cost

Every DFS response includes a `cost` field. The `CostTracker` on the singleton client sums these per `main.py` invocation and raises `DataForSEOBudgetExceeded` if the per-run cap is hit. Defaults: $1.00 cost cap, 50 calls per run. Override via env vars (`DATAFORSEO_MAX_COST_PER_RUN`, `DATAFORSEO_MAX_CALLS_PER_RUN`) if you need to run a deliberate big batch.

Account balance is visible at the DFS dashboard. `--mode validate` prints the current balance.

---
Last updated: 2026-05-26
