# AI Learning Subagents

Multi-agent system that finds SEO opportunities, drafts articles for [draftandarc.com](https://www.draftandarc.com), and measures how they perform after publishing.

## Flow

```
propose → pick → write + PR → publish → mark-published → measure
```

1. **`make propose`** — generates topic candidates, each scored with real DataForSEO data (search volume, difficulty, live SERP read), into `data/candidates.md`.
2. **Pick** — open `data/candidates.md`, change `[ ]` to `[x]` on the ones you want, edit titles/angles freely.
3. **Write + PR** — draft the picked articles into `data/drafts/` and open a PR to the blog repo.
4. **Publish** — review + merge the PR.
5. **`make mark-published ID=<slug>`** — once it's live.
6. **`make measure`** — ~1 week later; writes a perf brief that feeds the next round.

- Edit `data/editorial_focus.md` to steer what `propose` suggests (audience, topic areas, exclusions).
- `make weekly` is the older auto-planner (research → plan 4 articles). Still works, but `propose → pick` is preferred — it stopped the system churning out near-duplicate topics.
- Wiring ticked candidates straight to drafts (a `produce` step) is not yet a single command; for now `make article` writes the next *planned* calendar entry.

## Setup

**1. Install**
```bash
uv sync
```

**2. Fill `.env`** — `cp .env.example .env`

| Var | What |
|-----|------|
| `OPENAI_API_KEY` | LLM (default model: `gpt-5.4-mini`) |
| `TAVILY_API_KEY` | Web research |
| `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` | Keyword + SERP data |
| `GH_REPO` | Blog repo for auto-PR (e.g. `https://github.com/Apsides-Labs/draftnarc`) |
| `GSC_SITE_URL` | e.g. `sc-domain:draftandarc.com` — `measure` only |
| `GA4_PROPERTY_ID` | Numeric GA4 property ID — `measure` only |

**3. Google auth** (only needed for `make measure`)

One-time: create a Desktop OAuth client in GCP (project `draftandarc-seo-measurement` → APIs & Services → Credentials → OAuth client ID → Desktop app), download it to `~/.config/draftandarc/oauth-client.json`. Then:
```bash
bash scripts/gcloud-adc-login.sh
```

**4. Validate**
```bash
make validate
```

### Troubleshooting: Google login

- **`Reauthentication is needed`** → ADC token expired; re-run `bash scripts/gcloud-adc-login.sh`. Normal and expected.
- **Always use the script** — never paste the raw `gcloud … --scopes=…`; the long line wraps into a real space and breaks the scopes (`unrecognized arguments`).
- **"This app is blocked" / "provide your own client ID"** → you ran plain `gcloud auth application-default login`. Google blocks its *default* client for these scopes; the script passes our own OAuth client via `--client-id-file`, which fixes it.
- **`oauth-client.json` missing** → recreate it (Setup step 3). It's a Desktop OAuth client (`"installed"` type), **not** a service-account key.
- Auth only affects `make measure` — `propose` and `article` work without it.

## Commands

```bash
make propose [COUNT=12]                       # SEO-scored candidates → data/candidates.md
make article                                  # write next planned calendar entry → draft + blog PR
make measure                                  # GSC + GA4 perf brief (28 days)
make mark-published ID=<slug> [URL=… DATE=…]  # mark a calendar entry live
make list-calendar                            # all entries with status + live URL
make validate                                 # check all API credentials
make weekly                                   # legacy: auto-plan 4 articles
```

Custom measurement window: `uv run python main.py --mode measure --days 90`

## File layout

```
data/
  editorial_focus.md          — steers `propose` (audience, topics, exclusions)
  candidates.md               — proposed topics + SEO data; tick [x] to pick
  content_calendar.json       — source of truth for article status
  drafts/                     — article drafts (YYYY-MM-DD-slug.md)
  measurement_brief.{md,html} — latest perf brief (md auto-read by weekly)

agents/    — orchestrator + propose / research / seo / writing agents
services/  — dataforseo, seo_analysis, dedup, gsc, ga4, calendar, candidates, file I/O
tools/     — @tool wrappers for the research agents
scripts/gcloud-adc-login.sh   — Google ADC login helper
docs/playbooks/seo/           — SEO strategy playbooks
```
