# What This Plan Gives You — Plain English

A short, friendly summary of the 42-task implementation plan in `2026-05-20-seo-measurement-implementation.md`. Read this to know what you're getting. Read the long plan only when you (or an agent) is about to execute a task.

---

## In one sentence

After this plan ships, the marketing-agent system stops being an AI that writes into the void and starts being an AI that **learns from its own results**.

## What changes

Right now the system can plan and draft articles, but it has no idea whether they actually work once they're live. After the plan:

- A new `measure` mode pulls real performance data each week from Google Search Console, Google Analytics 4, and DataForSEO.
- You get an **HTML dashboard** showing which articles are getting search traffic, what people are searching to find them, where they rank, and what they do after they arrive.
- The next week's article ideas are **informed by what worked**, not guessed.

## The new weekly rhythm

```
setup    (run once)        →  reads your product code + competitors
weekly   (every week)      →  plans 4 new articles, now smarter
article  (per article)     →  drafts one, opens a blog PR
measure  (every week)      →  reads GSC + GA4 + DataForSEO, writes the dashboard
validate (one-off check)   →  confirms all credentials work
```

## What the dashboard looks like

`data/measurement_brief.html` — open it in your browser. You'll see:

- **Glossary** — every metric explained in plain English. Re-read until familiar.
- **Headline numbers** — totals across all blog articles.
- **Per-article cards** — green / yellow / red badges per metric, with a one-line "why this score" next to each.
- **Gap opportunities** — keywords you accidentally rank for that you didn't target. Easy follow-up wins.
- **Recommended actions** — a ranked to-do list ("rewrite the title of X", "write a follow-up on Y").

## Cost

About **$0.10–0.30 per week** in DataForSEO usage. $50 funds roughly a year. A hard **$1-per-run safety cap** means a bug can't suddenly drain the budget. Everything else (Google APIs, OpenAI, etc.) is unchanged.

## What success looks like a month from now

1. You run `make weekly` → 4 article ideas, picked based on what worked last week.
2. You run `make article` a few times → drafts + auto-PRs to the blog repo.
3. After publishing, you run `make measure` → open the HTML dashboard in your browser, see what's working.
4. Next week's `make weekly` reads last week's brief automatically. Loop closes.

---

## What you need before we start

A step-by-step pre-flight checklist. Do these in order. Total ~30 minutes.

### Step 1 — Set up DataForSEO (~5 min)

1. Go to `app.dataforseo.com` and sign up with your work email.
2. Confirm your email and log in.
3. Go to **Billing** → top up your account with **$50** (PayPal or card).
4. Go to **Profile → API access**. Copy two things and keep them handy:
   - **API Login** (your account email)
   - **API Password** (a long random string — NOT your dashboard login password)

### Step 2 — Confirm Google Search Console access (~2 min)

1. Open `search.google.com/search-console`.
2. Click the property dropdown (top left). You should see **`draftandarc.com`** listed.
3. If you don't see it: click **Add property** → **Domain** → enter `draftandarc.com` → follow Google's DNS verification steps. Talk to whoever manages your DNS if needed.

### Step 3 — Confirm GA4 access (~2 min)

1. Open `analytics.google.com`.
2. Click the property dropdown (top left). You should see the **Draft and Arc** property listed.
3. Click **Admin** (gear icon, bottom left). Under **Property settings**, copy the **Property ID** (a 9-or-10-digit number like `123456789`). Keep it handy.
4. If you can't access Admin: ask whoever set up GA4 to add you as an **Editor**.

### Step 4 — Create the Google Cloud project (~10 min)

The implementation plan walks you through this in detail (Task 17 + playbook). Short version:

1. Go to `console.cloud.google.com`. Create a new project called `draftandarc-seo-measurement`.
2. Enable two APIs in the project: **Google Search Console API** and **Google Analytics Data API**.
3. Create a service account called `seo-measurement`. Download its JSON key.
4. Move the JSON to `~/.config/draftandarc/gcp-service-account.json` (outside the repo so it can never be committed by accident).
5. Grant the service account access:
   - In Search Console → Settings → Users → add the service account email as **Restricted**.
   - In GA4 → Admin → Property access management → add the service account email as **Viewer**.

### Step 5 — Add credentials to `.env` (~2 min)

Open `.env` in this repo and add (substitute your real values):

```dotenv
DATAFORSEO_LOGIN=your-account-email
DATAFORSEO_PASSWORD=your-api-password-from-step-1
GOOGLE_APPLICATION_CREDENTIALS=/Users/<you>/.config/draftandarc/gcp-service-account.json
GSC_SITE_URL=sc-domain:draftandarc.com
GA4_PROPERTY_ID=123456789
```

The `sc-domain:` prefix on `GSC_SITE_URL` is mandatory for domain-level Search Console properties.

### Step 6 — Verify everything is wired (~5 sec)

Once the plan is executed up to Task 19 (about a third of the way through), run:

```bash
make validate
```

You'll see three lines: `[PASS] DataForSEO`, `[PASS] GSC`, `[PASS] GA4`. If any says `[FAIL]`, the error message tells you which step to revisit.

---

## What happens *during* the plan (just so nothing surprises you)

- The plan adds a couple of new Python dependencies (DataForSEO HTTP client, Google API libraries, Jinja2 for the dashboard template). `uv sync` handles it.
- It drops two old dependencies (pytrends, SerpAPI) and one config field (`serpapi_api_key`). If you have a SerpAPI subscription, you can cancel it once the plan is done.

## What's NOT in this plan (but worth knowing)

The blog frontend is a separate dependency, owned by the FE team. The Python plan ships and runs fine without it — but the dashboard will say "no blog content live yet" until:

- Blog routes exist on `draftandarc.com`.
- The `signup_cta_click` event fires on the blog CTA (one-line FE change).
- At least one article is published and indexed by Google (~2–3 weeks for real data to show up).

The full ask for the FE team is in `docs/handoffs/2026-05-24-blog-ga4-fe-request.md` *(not yet recreated — let me know if you want it back)*.

---

*Full implementation plan (42 tasks, technical): `docs/superpowers/plans/2026-05-20-seo-measurement-implementation.md`*
*Design spec (the "why" behind every decision): `docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md`*
