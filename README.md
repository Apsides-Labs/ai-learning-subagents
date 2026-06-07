# AI Learning Subagents

Multi-agent system that researches SEO opportunities, plans and drafts articles for [draftandarc.com](https://www.draftandarc.com), and measures how they perform after publishing.

## What it does

```
weekly  →  plan 4 SEO-targeted articles (keyword research + content calendar)
article →  write + fact-check one draft, open a GitHub PR to the blog repo
measure →  pull GSC + GA4 data, generate a performance brief injected into next weekly run
```

Each weekly run automatically reads the last measurement brief so the SEO agent improves article strategy over time.

## Setup

**1. Install dependencies**
```bash
uv sync
```

**2. Copy and fill `.env`**
```bash
cp .env.example .env
```

Required vars:
| Var | What |
|-----|------|
| `OPENAI_API_KEY` | LLM (default model: gpt-4o-mini) |
| `TAVILY_API_KEY` | Web research |
| `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` | Keyword data |
| `GSC_SITE_URL` | e.g. `sc-domain:draftandarc.com` |
| `GA4_PROPERTY_ID` | Numeric GA4 property ID |
| `GH_REPO` | Blog repo for auto-PR (e.g. `https://github.com/Apsides-Labs/draftnarc`) |

**3. Authenticate with Google (GSC + GA4)**

Requires a custom OAuth client because Google blocks the default gcloud client ID for `webmasters.readonly` and `analytics.readonly`.

One-time GCP setup:
1. GCP console → project `draftandarc-seo-measurement`
2. APIs & Services → Credentials → Create → OAuth client ID → Desktop app → Download JSON
3. Save to `~/.config/draftandarc/oauth-client.json`

Then run:
```bash
bash scripts/gcloud-adc-login.sh
```

**4. Validate everything works**
```bash
make validate
```

## The repeating cycle

```
make measure → make weekly → make article → publish → make mark-published
     ↑                                                         │
     └──────────────────── wait ~1 week ──────────────────────┘
```

- `make measure` writes `data/measurement_brief.md`, which is automatically injected into the next `make weekly` so the SEO agent knows what's working
- always run `make measure` right before `make weekly`, not before `make article`
- wait at least a week after publishing before measuring — Google needs time to index and accumulate data

## Commands

```bash
make weekly    # research + plan 4 articles → data/content_calendar.json
make article   # write next planned article → data/drafts/YYYY-MM-DD-slug.md
               # also opens a PR to the blog repo automatically
```

Review the draft, merge the PR, publish to the blog.

**After publishing each article:**
```bash
make mark-published ID=<slug>
# Example:
make mark-published ID=lecture-notes-verbatim
# Custom date (if published in the past):
make mark-published ID=tutorial-hell-progress DATE=2026-04-27
```

**To see performance data:**
```bash
make measure
```

Pulls last 28 days of GSC impressions/clicks/position and GA4 engagement. Writes:
- `data/measurement_brief.md` — agent-facing summary (auto-injected into next `make weekly`)
- `data/measurement_brief.html` — human dashboard, open in browser

To change the window:
```bash
uv run python main.py --mode measure --days 90
```

## Checking the calendar

```bash
make list-calendar    # shows all entries with status and live URL
```

## File layout

```
data/
  content_calendar.json   — single source of truth for article status
  drafts/                 — generated article drafts (YYYY-MM-DD-slug.md)
  measurement_brief.md    — latest perf brief (auto-read by weekly agent)
  measurement_brief.html  — human-readable dashboard

agents/                   — orchestrator + individual agent definitions
services/                 — GSC, GA4, DataForSEO, calendar, file I/O clients
tools/                    — @tool wrappers exposed to research agents
scripts/
  gcloud-adc-login.sh     — ADC login helper for Google APIs
docs/playbooks/seo/       — SEO strategy playbooks
```
