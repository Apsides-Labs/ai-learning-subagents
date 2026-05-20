# SEO Measurement Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the measurement spine to the marketing-agent system: replace SerpAPI + pytrends with DataForSEO, add Google Search Console + GA4 integrations, introduce `--mode measure` with dual-output briefs, and wire the feedback loop back into the SEO agent.

**Architecture:** A new 4th mode (`measure`) that produces `data/measurement_brief.{md,html}` from GSC + GA4 + DataForSEO Labs. The MD brief is auto-included in the next weekly SEO agent context via a structural `## MEASUREMENT BRIEF` delimiter. Code-shape is "Approach A" from the spec: tool-centric, minimal restructure, each rollout step independently shippable and revertable.

**Tech Stack:** Python 3.12+, langchain + langchain-openai, httpx (async HTTP for DataForSEO), google-api-python-client (sync, wrapped in `asyncio.to_thread`) for GSC, google-analytics-data (`BetaAnalyticsDataAsyncClient`) for GA4, jinja2 for HTML rendering, pydantic + dataclasses for typed schemas, pytest + pytest-asyncio for tests.

**Reference spec:** `docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md`. Read sections 3–9 before starting; the plan implements that design exactly.

---

## File Structure

**New packages (created in Task 1 and Task 23):**
- `tools/` (converted from `tools.py`) — `__init__.py` re-exports legacy names + `dataforseo.py` for new @tool wrappers
- `renderers/` — `__init__.py`, `measurement_md.py`, `measurement_html.py`, `templates/measurement.html.j2`

**New services (one file per external integration):**
- `services/dataforseo_client.py` — singleton HTTP client + `CostTracker` + `DataForSEOBudgetExceeded`
- `services/gsc_client.py` — Search Console (sync internals + async public API)
- `services/ga4_client.py` — GA4 (async, two-report merge)
- `services/scoring.py` — pure threshold functions, returns `Label`

**New models / agents:**
- `models/measurement.py` — `MeasurementReport`, `ScoredArticlePerformance`, `MetricScore`, etc., plus `report_to_synthesis_input()` and `normalize_url()` helpers
- `agents/measurement_agent.py` — deterministic fetch + LLM synthesis pipeline

**New prompts:**
- `prompts/md/chains/measurement_synthesis.md`

**New tests (one per module):**
- `tests/test_dataforseo_client.py`, `tests/test_dataforseo_tools.py`, `tests/test_gsc_client.py`, `tests/test_ga4_client.py`, `tests/test_scoring.py`, `tests/test_measurement.py`, `tests/test_measurement_agent.py`, `tests/test_renderers.py`, `tests/test_file_service.py`, `tests/test_calendar_mark_published.py`, `tests/test_orchestrator_wiring.py`
- `tests/fixtures/*.json` — realistic API response samples

**New docs:**
- `docs/playbooks/seo/00-overview.md` through `06-when-to-refresh-vs-rewrite-vs-kill.md` (7 files)
- `CLAUDE.md`

**Modified:**
- `services/file_service.py` — add `atomic_write_text`, `MEASUREMENT_BRIEF_MD_PATH`, `MEASUREMENT_BRIEF_HTML_PATH`
- `services/calendar_service.py` — use `atomic_write_text`, add `mark_published`
- `models/article.py` — add `published_at` and `live_url` fields
- `output_schemas.py` — add measurement schemas, add `seo_coverage_note` to `SEOOutput`
- `agents/seo_agent.py` — new tool list, budget try/except, prompt the synthesis LLM about coverage_note
- `agents/orchestrator.py` — `## MEASUREMENT BRIEF` delimiter, `run_measure()`, `mark_published()`
- `prompts/md/agents/seo_system.md` — `TOOLS` section + `PAST-PERFORMANCE CONTEXT` section
- `prompts/md/chains/seo_synthesis.md` — DFS metric names + coverage-note instruction
- `main.py` — `--mode measure`, `--mode validate`, `--mark-published`
- `config.py` + `.env.example` — DFS + GSC + GA4 settings
- `pyproject.toml` — deps + Hatch wheel packages list
- `Makefile` — `measure`, `validate` targets

---

## Task 0: Verify DataForSEO endpoint pricing (manual, no code)

**Why this task exists:** The spec's Section 4 cost table is an estimate. Bulk Keyword Difficulty pricing in particular has been uncertain (~$0.01 vs ~$0.10 per 1000 kw). Before writing the client code, confirm prices against the live dashboard so the `MAX_COST_PER_RUN` default in Task 7 ($1.00) is reasonable.

- [ ] **Step 1: Log into the DataForSEO dashboard**

Open `app.dataforseo.com` and sign in with the account credentials you'll use in `.env`.

- [ ] **Step 2: Verify per-call cost for the 5 endpoints we use**

Confirm prices on each pricing page (Account → Pricing or API → individual endpoint docs):

| Endpoint | Expected from spec | Actual (verify) |
|---|---|---|
| SERP / Google / Organic / Live Advanced | ~$0.002/query | _____ |
| Keywords Data / Google Ads / Search Volume | ~$0.05/1000 kw | _____ |
| Labs / Google / Bulk Keyword Difficulty | ~$0.01/1000 kw | _____ |
| Labs / Google / Keyword Suggestions | ~$0.01/task | _____ |
| Labs / Google / Ranked Keywords for Domain | ~$0.02/task | _____ |

- [ ] **Step 3: If any number diverges materially, update the spec**

Open `docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md`. Find the endpoint table in Section 4. Replace the diverged price(s) with the verified rate. Commit:

```bash
git add docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md
git commit -m "docs: update DataForSEO pricing after dashboard verification"
```

- [ ] **Step 4: Reconsider `MAX_COST_PER_RUN`**

If the new prices imply that a normal weekly batch costs >$0.30 (the high end of the spec's projection), bump `MAX_COST_PER_RUN` default in Task 7's code from `1.00` to ~3× normal usage. The cap is meant to catch bugs, not normal usage.

- [ ] **Step 5: Pre-flight check — pandas isn't used outside the deleted tests**

Run: `grep -rn "import pandas\|from pandas" --include='*.py' .`
Expected: only references in `tests/test_tools.py::test_google_trends_*` (which are deleted in Task 2). If any other file imports pandas, surface this to the user before proceeding — Task 2 will break things.

- [ ] **Step 6: Acknowledge — no commit required**

This task changes nothing in the repo unless Step 3 fired. Continue to Task 1.

---

## Task 1: Convert `tools.py` into a `tools/` package

**Why first:** Python cannot have `tools.py` and `tools/` coexist. Every later task that imports from `tools` depends on this. Existing imports (`from tools import jina_reader, tavily_search_tool, ...` in `agents/research_agent.py`; `from tools import tavily_search_tool, people_also_ask, google_trends` in `agents/seo_agent.py`) must keep working after this conversion.

**Important:** `agents/seo_agent.py` imports `people_also_ask` and `google_trends` and won't be updated to drop them until Task 14. To prevent the repo from being import-broken for the entire Task 2–13 stretch, this task keeps **deprecation shims** for those two names in `tools/__init__.py` — they exist as callable stubs that raise `NotImplementedError` if invoked. The shims are deleted in Task 14 as part of the SEO agent's tool list swap.

**Files:**
- Delete: `tools.py`
- Create: `tools/__init__.py`
- Test: `tests/test_tools_package.py`

- [ ] **Step 1: Read existing `tools.py`**

Run: `cat tools.py`

Confirm it contains: `jina_reader`, `google_trends`, `people_also_ask`, `list_codebase_files`, `read_codebase_file`, `tavily_search_tool`. The first three are the SEO-agent tools; the rest are research-agent tools.

- [ ] **Step 2: Write the failing import test**

Create `tests/test_tools_package.py`:

```python
"""Confirms the tools/ package re-exports legacy names after the tools.py → tools/ conversion.

The people_also_ask and google_trends shims exist but raise NotImplementedError
when called. They are removed in Task 14 once the SEO agent stops importing them.
"""

import pytest


def test_research_agent_imports_still_work():
    from tools import jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file
    assert callable(jina_reader)
    assert tavily_search_tool is not None
    assert callable(list_codebase_files)
    assert callable(read_codebase_file)


def test_seo_agent_imports_resolve_to_shims():
    """seo_agent.py still imports these until Task 14; the shims keep the import alive."""
    from tools import people_also_ask, google_trends
    assert callable(people_also_ask)
    assert callable(google_trends)


def test_shims_raise_when_invoked():
    """Calling a shim is a programmer error — the SEO agent's tool list is swapped in Task 14."""
    from tools import people_also_ask, google_trends
    with pytest.raises(NotImplementedError):
        people_also_ask.invoke({"query": "x"})
    with pytest.raises(NotImplementedError):
        google_trends.invoke({"keyword": "x"})
```

- [ ] **Step 3: Run the test to confirm current state**

Run: `uv run pytest tests/test_tools_package.py -v`
Expected: FAIL on `test_shims_raise_when_invoked` (current `tools.py` provides real implementations) and FAIL on `test_seo_agent_imports_resolve_to_shims` if pytest can't even import the test module because pytrends/SerpAPI aren't installed in your dev env — that's fine, the implementation step removes them.

- [ ] **Step 4: Create the `tools/` directory and move keepable code**

Run: `mkdir tools`

Create `tools/__init__.py` with the kept functions PLUS deprecation shims:

```python
"""Tools package. Re-exports the research-agent tools.

DataForSEO tools live in `tools.dataforseo` and are imported by the SEO agent
directly from that module after Task 14.

The people_also_ask and google_trends shims below exist solely to keep
`agents/seo_agent.py` importable between Tasks 2 and 13 (the SEO agent
swaps its tool list in Task 14). They raise NotImplementedError when
invoked — if anything actually calls them, that's a bug.
"""

from pathlib import Path
import httpx
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from config import settings


@tool
async def jina_reader(url: str) -> str:
    """Read the text content of any URL using Jina AI Reader. Use for competitor pages."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"https://r.jina.ai/{url}")
        response.raise_for_status()
        return response.text


@tool
def list_codebase_files(directory: str = "") -> str:
    """List Python files in the Draft and Arc codebase. Use to discover what to read."""
    base = Path(settings.codebase_path) / directory
    if not base.exists():
        return f"Directory not found: {directory}"
    files = [
        str(f.relative_to(Path(settings.codebase_path)))
        for f in base.rglob("*.py")
        if "__pycache__" not in str(f)
    ]
    return "\n".join(sorted(files)[:60])


@tool
def read_codebase_file(relative_path: str) -> str:
    """Read a specific file from the Draft and Arc codebase. Use for extracting product facts."""
    path = Path(settings.codebase_path) / relative_path
    if not path.exists():
        return f"File not found: {relative_path}"
    return path.read_text(encoding="utf-8")


tavily_search_tool = TavilySearch(max_results=5)


# --- Deprecation shims (deleted in Task 14) ---
# Reason these exist at all: agents/seo_agent.py still does
# `from tools import people_also_ask, google_trends`. If we delete those
# names here in Task 1, the import fails until Task 14. The shims keep
# the import alive but raise loudly if called.

@tool
def people_also_ask(query: str) -> str:
    """DEPRECATED. Removed in Task 14 — SEO agent uses dfs_serp_live_advanced."""
    raise NotImplementedError(
        "people_also_ask was removed. The SEO agent should be calling "
        "dfs_serp_live_advanced from tools.dataforseo (Task 14)."
    )


@tool
def google_trends(keyword: str) -> str:
    """DEPRECATED. Removed in Task 14 — SEO agent uses dfs_keyword_suggestions + dfs_bulk_keyword_data."""
    raise NotImplementedError(
        "google_trends was removed. The SEO agent should be calling "
        "dfs_keyword_suggestions / dfs_bulk_keyword_data from tools.dataforseo (Task 14)."
    )
```

- [ ] **Step 5: Delete the old `tools.py`**

Run: `rm tools.py`

- [ ] **Step 6: Run the test to verify both checks pass**

Run: `uv run pytest tests/test_tools_package.py -v`
Expected: both tests PASS.

- [ ] **Step 7: Run the full test suite to verify nothing else broke**

Run: `uv run pytest -x -q`
Expected: existing tests that touched `people_also_ask` / `google_trends` (in `tests/test_tools.py`) now fail. That's expected; Task 2 fixes them. The rest must pass.

- [ ] **Step 8: Commit**

```bash
git add tools/ tests/test_tools_package.py
git rm tools.py
git commit -m "refactor: convert tools.py into tools/ package + shim deprecated tools

Python won't let tools.py and tools/ coexist; later tasks add
tools/dataforseo.py. The package's __init__.py re-exports the
research-agent tools so agents/research_agent.py keeps working.

people_also_ask and google_trends are stubs that raise
NotImplementedError. They exist only to keep agents/seo_agent.py
importable until Task 14 swaps its tool list. Deleted in Task 14."
```

---

## Task 2: Remove obsolete tests and dependencies

**Why now:** Task 1 left `tests/test_tools.py::test_google_trends_*` failing because the functions no longer exist. Clean them up immediately so the suite is green before adding new code.

**Files:**
- Modify: `tests/test_tools.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove the dead tests**

Open `tests/test_tools.py`. Delete these test functions entirely:
- `test_google_trends_rising`
- `test_google_trends_no_data`

Also remove the unused `import pandas as pd` lines inside those functions (they were local imports inside the test bodies — confirm none remain at module scope).

Keep all other tests: `test_jina_reader_returns_text`, `test_list_codebase_files`, `test_read_codebase_file`, `test_read_codebase_file_not_found`.

- [ ] **Step 2: Verify the file**

Run: `grep -n "google_trends\|people_also_ask\|pytrends\|pandas" tests/test_tools.py`
Expected: zero matches.

- [ ] **Step 3: Verify pandas isn't used elsewhere**

Run: `grep -rn "import pandas" --include='*.py' .`
Expected: zero matches. (If pandas is imported anywhere else, stop and surface to the user — the dep removal in step 4 will break things.)

- [ ] **Step 4: Update `pyproject.toml`**

Open `pyproject.toml`. In the `[project] dependencies` list:
- Remove `"google-search-results>=2.4"` (the SerpAPI client)
- Remove `"pytrends>=4.9"`
- Remove `"tavily-python>=0.3"` ONLY IF it's not used by `langchain-tavily` (verify with `grep -rn "import tavily" --include='*.py' .` — keep if found). The codebase uses `langchain_tavily`, which already pulls `tavily-python` transitively, but removal is out of scope for this task to avoid surprises.

Result in the dependencies section:

```toml
dependencies = [
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "langchain-community>=0.3",
    "langgraph>=0.2",
    "tavily-python>=0.3",
    "pydantic-settings>=2.0",
    "aiofiles>=24.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "langchain-tavily>=0.2.18",
]
```

- [ ] **Step 5: Sync dependencies**

Run: `uv sync`
Expected: pyproject.lock updates; pandas/pytrends/google-search-results disappear from the lockfile.

- [ ] **Step 6: Run the test suite to confirm green**

Run: `uv run pytest -x -q`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/test_tools.py pyproject.toml uv.lock
git commit -m "chore: remove pytrends and SerpAPI deps + their tests

google_trends and people_also_ask are deleted (Task 1). pandas was
only transitively pulled by pytrends and is unused elsewhere.
SerpAPI's google-search-results goes too."
```

---

## Task 3: Add `atomic_write_text` helper to `file_service`

**Why now:** Every later task that writes calendar JSON or brief files goes through this. Adding it before `--mark-published` (Task 27) and the renderers (Tasks 24–25) means they can use it from day one.

**Files:**
- Modify: `services/file_service.py`
- Create: `tests/test_file_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_file_service.py`:

```python
"""Atomic write semantics: target file appears all-or-nothing, never half-written."""

import os
from pathlib import Path

import pytest


async def test_atomic_write_text_writes_content(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "out.txt"
    await atomic_write_text(target, "hello world")

    assert target.read_text(encoding="utf-8") == "hello world"


async def test_atomic_write_text_creates_parent_dirs(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "nested" / "deep" / "out.txt"
    await atomic_write_text(target, "hello")

    assert target.read_text(encoding="utf-8") == "hello"


async def test_atomic_write_text_does_not_leave_tmp_file_on_success(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "out.txt"
    await atomic_write_text(target, "hello")

    siblings = list(tmp_path.iterdir())
    # Only the target file should exist; no leftover .tmp file.
    assert siblings == [target]


async def test_atomic_write_text_overwrites_existing(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "out.txt"
    target.write_text("old content")
    await atomic_write_text(target, "new content")

    assert target.read_text(encoding="utf-8") == "new content"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_file_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'atomic_write_text'` on each test.

- [ ] **Step 3: Implement `atomic_write_text`**

Open `services/file_service.py`. Add at the bottom:

```python
import os
import uuid


async def atomic_write_text(path: Path, content: str) -> None:
    """Write text to `path` atomically.

    Writes to a sibling tmp file first, then `os.replace`s it onto the
    target. A crash mid-write leaves either the old file intact or
    nothing (if the target didn't exist before) — never a half-written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            await f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Add the new path constants**

Still in `services/file_service.py`, near the existing path constants:

```python
MEASUREMENT_BRIEF_MD_PATH = DATA_DIR / "measurement_brief.md"
MEASUREMENT_BRIEF_HTML_PATH = DATA_DIR / "measurement_brief.html"
```

- [ ] **Step 5: Run the tests to verify pass**

Run: `uv run pytest tests/test_file_service.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/file_service.py tests/test_file_service.py
git commit -m "feat: add atomic_write_text helper and measurement brief paths

Writes via tmp file + os.replace. Used by --mark-published, the
calendar service, and the brief renderers so a crash mid-write never
leaves a half-written file."
```

---

## Task 4: Migrate `save_calendar` to use `atomic_write_text`

**Why now:** Same reason — every later task touching the calendar should already be on atomic semantics. This task does NOT add `mark_published` yet (Task 27).

**Files:**
- Modify: `services/calendar_service.py`
- Modify: `tests/test_services.py` (verify existing behavior unchanged)

- [ ] **Step 1: Update `save_calendar` to use atomic write (preserve current signatures)**

Open `services/calendar_service.py`. The only change is to route `save_calendar` through `atomic_write_text`. Every other function, including `update_status`'s `pr_url` parameter (added by the upstream auto-blog-PR feature), is preserved verbatim:

```python
import json
from pathlib import Path
from typing import Optional
import aiofiles
from models.article import ArticleStatus, ContentCalendarEntry
from services.file_service import atomic_write_text

CALENDAR_PATH = Path("data/content_calendar.json")


async def load_calendar() -> list[ContentCalendarEntry]:
    if not CALENDAR_PATH.exists():
        return []
    async with aiofiles.open(CALENDAR_PATH, "r", encoding="utf-8") as f:
        data = json.loads(await f.read())
    return [ContentCalendarEntry(**entry) for entry in data]


async def save_calendar(entries: list[ContentCalendarEntry]) -> None:
    content = json.dumps([e.model_dump() for e in entries], indent=2)
    await atomic_write_text(CALENDAR_PATH, content)


async def add_entries(new_entries: list[ContentCalendarEntry]) -> None:
    entries = await load_calendar()
    existing_ids = {e.id for e in entries}
    for entry in new_entries:
        if entry.id not in existing_ids:
            entries.append(entry)
    await save_calendar(entries)


async def next_planned() -> Optional[ContentCalendarEntry]:
    entries = await load_calendar()
    return next((e for e in entries if e.status == ArticleStatus.planned), None)


async def update_status(
    entry_id: str,
    status: ArticleStatus,
    draft_path: Optional[str] = None,
    pr_url: Optional[str] = None,
) -> None:
    entries = await load_calendar()
    for entry in entries:
        if entry.id == entry_id:
            entry.status = status
            if draft_path is not None:
                entry.draft_path = draft_path
            if pr_url is not None:
                entry.pr_url = pr_url
    await save_calendar(entries)
```

- [ ] **Step 2: Run existing tests to confirm behavior is unchanged**

Run: `uv run pytest tests/test_services.py -v`
Expected: all PASS (round-trips read-mutate-write the same way; behavior is identical, only the write step is now atomic).

- [ ] **Step 3: Commit**

```bash
git add services/calendar_service.py
git commit -m "refactor: route save_calendar through atomic_write_text

No behavior change — just stops the truncate-and-write race that
could corrupt content_calendar.json on a crash mid-write."
```

---

## Task 5: Add DataForSEO config and dependencies

**Why now:** The DataForSEO client (Task 6) needs `settings.dataforseo_login`, `settings.dataforseo_password`, plus the env-overridable cost caps. Add them before writing the client.

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add settings to `config.py`**

Open `config.py`. Replace the `Settings` class:

```python
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(Path(__file__).parent / ".env")


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-5.4-mini"
    tavily_api_key: str
    codebase_path: str = "/Users/ilirgruda/Repo/Python/ai-learning"
    gh_repo: str = ""

    # DataForSEO (replaces SerpAPI + pytrends)
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_max_cost_per_run: float = 1.00
    dataforseo_max_calls_per_run: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
```

NOTE on the `gpt-5.4-mini` default: this is pre-existing and intentionally not changed in this plan. The spec Section 10 flags it as a known item to verify before the first real run.

- [ ] **Step 2: Update `.env.example`**

Open `.env.example`. Replace its full contents with:

```dotenv
# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Research (kept)
TAVILY_API_KEY=tvly-...

# Codebase to read product facts from
CODEBASE_PATH=/Users/ilirgruda/Repo/Python/ai-learning

# Blog repo for auto-PR publishing (kept from upstream auto-blog-PR feature)
GH_REPO=https://github.com/Apsides-Labs/draftnarc

# DataForSEO (new — replaces SerpAPI + pytrends)
DATAFORSEO_LOGIN=your-account-email
DATAFORSEO_PASSWORD=your-api-password
# Optional cost-cap overrides; defaults: $1.00 cost, 50 calls
# DATAFORSEO_MAX_COST_PER_RUN=1.00
# DATAFORSEO_MAX_CALLS_PER_RUN=50

# Google Search Console + GA4 (new — measurement, added later in the rollout)
# GOOGLE_APPLICATION_CREDENTIALS=/Users/ilirgruda/.config/draftandarc/gcp-service-account.json
# GSC_SITE_URL=sc-domain:draftandarc.com
# GA4_PROPERTY_ID=123456789
```

The `SERPAPI_API_KEY` line is gone. The Google service-account lines are commented out — they'll be uncommented in Task 17.

- [ ] **Step 3: Create the `renderers/` placeholder**

The `renderers/` package is fully populated in Tasks 23–24, but the Hatch wheel-packages list (next sub-step) will reference it now. Hatch requires the directory and its `__init__.py` to exist at registration time. Create the placeholder unconditionally:

```bash
mkdir -p renderers
```

Create `renderers/__init__.py` with one line of content (empty files trip some linters):

```python
"""Renderers for the measurement brief. Populated in Tasks 23-24."""
```

- [ ] **Step 4: Update Hatch packages in `pyproject.toml`**

Open `pyproject.toml`. Replace the wheel packages list:

```toml
[tool.hatch.build.targets.wheel]
packages = ["agents", "chains", "models", "prompts", "renderers", "services", "tests", "tools"]
```

- [ ] **Step 5: Sync dependencies**

Run: `uv sync`
Expected: no errors.

- [ ] **Step 6: Confirm settings import works**

Run: `uv run python -c "from config import settings; print(bool(settings.dataforseo_login or True), settings.dataforseo_max_cost_per_run)"`
Expected: `True 1.0`

- [ ] **Step 7: Commit**

```bash
git add config.py .env.example pyproject.toml renderers/__init__.py
git commit -m "feat: add DataForSEO settings + register tools and renderers packages

Adds DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, and the two cost-cap
overrides. Updates .env.example to the new exact final state.
Registers tools/ and renderers/ as Hatch wheel packages."
```

---

## Task 6: Implement `CostTracker` + `DataForSEOBudgetExceeded`

**Why split from the client:** Cost tracking is pure logic — easiest to test in isolation. The HTTP client (Task 7) then uses it.

**Files:**
- Create: `services/dataforseo_client.py` (partial — only `CostTracker` and the exception)
- Create: `tests/test_dataforseo_client.py` (partial)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dataforseo_client.py`:

```python
"""CostTracker + DataForSEOBudgetExceeded unit tests."""

import pytest


def test_cost_tracker_starts_at_zero():
    from services.dataforseo_client import CostTracker

    t = CostTracker(max_cost=1.0, max_calls=50)
    assert t.total_cost == 0.0
    assert t.total_calls == 0


def test_cost_tracker_records_calls():
    from services.dataforseo_client import CostTracker

    t = CostTracker(max_cost=1.0, max_calls=50)
    t.record(cost=0.002, endpoint="serp")
    t.record(cost=0.01, endpoint="kw_suggestions")

    assert t.total_calls == 2
    assert t.total_cost == pytest.approx(0.012)


def test_cost_tracker_raises_on_cost_cap():
    from services.dataforseo_client import CostTracker, DataForSEOBudgetExceeded

    t = CostTracker(max_cost=0.005, max_calls=50)
    t.record(cost=0.003, endpoint="a")
    with pytest.raises(DataForSEOBudgetExceeded) as exc:
        t.record(cost=0.003, endpoint="b")  # would cross the $0.005 cap

    assert "cost" in str(exc.value).lower()


def test_cost_tracker_raises_on_call_cap():
    from services.dataforseo_client import CostTracker, DataForSEOBudgetExceeded

    t = CostTracker(max_cost=10.0, max_calls=2)
    t.record(cost=0.0, endpoint="a")
    t.record(cost=0.0, endpoint="b")
    with pytest.raises(DataForSEOBudgetExceeded) as exc:
        t.record(cost=0.0, endpoint="c")

    assert "call" in str(exc.value).lower()


def test_cost_tracker_message_includes_recent_endpoints():
    """When the cap fires, the error should help debugging by naming recent endpoints."""
    from services.dataforseo_client import CostTracker, DataForSEOBudgetExceeded

    t = CostTracker(max_cost=10.0, max_calls=2)
    t.record(cost=0.0, endpoint="serp")
    t.record(cost=0.0, endpoint="kw_volume")
    with pytest.raises(DataForSEOBudgetExceeded) as exc:
        t.record(cost=0.0, endpoint="kw_difficulty")

    msg = str(exc.value)
    assert "serp" in msg and "kw_volume" in msg
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `uv run pytest tests/test_dataforseo_client.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `CostTracker`**

Create `services/dataforseo_client.py`:

```python
"""DataForSEO HTTP client + cost tracking.

The full client (HTTP + endpoints) is added in Task 7. This file currently
provides the CostTracker and DataForSEOBudgetExceeded exception, used by
the HTTP wrapper to enforce per-run budget caps.
"""

from collections import deque
from dataclasses import dataclass, field


class DataForSEOBudgetExceeded(RuntimeError):
    """Raised when the per-run cost or call cap is exceeded."""


@dataclass
class CostTracker:
    max_cost: float
    max_calls: int
    total_cost: float = 0.0
    total_calls: int = 0
    _recent: deque = field(default_factory=lambda: deque(maxlen=5))

    def record(self, *, cost: float, endpoint: str) -> None:
        prospective_cost = self.total_cost + cost
        prospective_calls = self.total_calls + 1

        if prospective_cost > self.max_cost:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO cost cap of ${self.max_cost:.2f} would be exceeded "
                f"(current ${self.total_cost:.4f} + ${cost:.4f}); "
                f"recent endpoints: {list(self._recent)}"
            )
        if prospective_calls > self.max_calls:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO call cap of {self.max_calls} would be exceeded "
                f"(current {self.total_calls} + 1); "
                f"recent endpoints: {list(self._recent)}"
            )

        self.total_cost = prospective_cost
        self.total_calls = prospective_calls
        self._recent.append(endpoint)
```

- [ ] **Step 4: Run the tests to verify pass**

Run: `uv run pytest tests/test_dataforseo_client.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/dataforseo_client.py tests/test_dataforseo_client.py
git commit -m "feat: add DataForSEO CostTracker + DataForSEOBudgetExceeded

Per-run cost and call caps. The tracker lives on a singleton client
(Task 7) so caps apply across an entire main.py invocation."
```

---

## Task 7: Implement the `DataForSEOClient` singleton

**Why now:** The @tool wrappers (Tasks 8–11) all call methods on this client. It's the foundation for the SEO agent's new tool list.

**Files:**
- Modify: `services/dataforseo_client.py`
- Modify: `tests/test_dataforseo_client.py`
- Create: `tests/fixtures/dfs_serp_response.json`

- [ ] **Step 1: Capture a representative SERP fixture**

Create `tests/fixtures/` if it doesn't exist:
```bash
mkdir -p tests/fixtures
```

Create `tests/fixtures/dfs_serp_response.json` (minimal but realistically shaped — matches the structure DataForSEO returns):

```json
{
  "version": "0.1.20240101",
  "status_code": 20000,
  "status_message": "Ok.",
  "time": "0.5 sec.",
  "cost": 0.002,
  "tasks_count": 1,
  "tasks_error": 0,
  "tasks": [
    {
      "id": "task-id-1",
      "status_code": 20000,
      "status_message": "Ok.",
      "result": [
        {
          "keyword": "how to get rid of tutorial hell",
          "location_code": 2840,
          "language_code": "en",
          "check_url": "https://www.google.com/search?q=...",
          "items_count": 2,
          "items": [
            {
              "type": "organic",
              "rank_absolute": 1,
              "domain": "reddit.com",
              "title": "How do you escape tutorial hell?",
              "description": "Discussion thread about escaping tutorial hell.",
              "url": "https://www.reddit.com/r/learnprogramming/comments/abc/tutorial_hell/"
            },
            {
              "type": "people_also_ask_element",
              "items": [
                {"title": "What is tutorial hell?"},
                {"title": "How do you escape tutorial hell?"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing client tests**

Append to `tests/test_dataforseo_client.py`:

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_get_client_returns_singleton():
    """Two calls return the same instance — required for the cost cap to be process-scoped."""
    from services import dataforseo_client as mod
    mod._client = None  # reset for test isolation

    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "user@example.com"
        mock_settings.dataforseo_password = "pass"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        a = mod.get_client()
        b = mod.get_client()
        assert a is b


async def test_post_records_cost_from_response():
    from services import dataforseo_client as mod
    mod._client = None

    response_json = _load_fixture("dfs_serp_response.json")
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=response_json)
    mock_response.raise_for_status = MagicMock()

    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "user@example.com"
        mock_settings.dataforseo_password = "pass"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = mod.get_client()
        client._http = MagicMock()
        client._http.post = AsyncMock(return_value=mock_response)

        result = await client.post("/v3/serp/google/organic/live/advanced", json_body=[{"keyword": "x"}])

        assert client.tracker.total_calls == 1
        assert client.tracker.total_cost == pytest.approx(0.002)
        assert result == response_json
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_dataforseo_client.py -v`
Expected: new tests FAIL with `AttributeError: module 'services.dataforseo_client' has no attribute 'get_client'`.

- [ ] **Step 4: Implement the singleton client**

Open `services/dataforseo_client.py`. Replace its contents with:

```python
"""DataForSEO HTTP client + cost tracking.

Module-level singleton via get_client(). All @tool wrappers in
tools/dataforseo.py call into the same instance so the CostTracker
cap applies across one main.py invocation.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from config import settings


class DataForSEOBudgetExceeded(RuntimeError):
    """Raised when the per-run cost or call cap is exceeded."""


@dataclass
class CostTracker:
    max_cost: float
    max_calls: int
    total_cost: float = 0.0
    total_calls: int = 0
    _recent: deque = field(default_factory=lambda: deque(maxlen=5))

    def record(self, *, cost: float, endpoint: str) -> None:
        prospective_cost = self.total_cost + cost
        prospective_calls = self.total_calls + 1

        if prospective_cost > self.max_cost:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO cost cap of ${self.max_cost:.2f} would be exceeded "
                f"(current ${self.total_cost:.4f} + ${cost:.4f}); "
                f"recent endpoints: {list(self._recent)}"
            )
        if prospective_calls > self.max_calls:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO call cap of {self.max_calls} would be exceeded "
                f"(current {self.total_calls} + 1); "
                f"recent endpoints: {list(self._recent)}"
            )

        self.total_cost = prospective_cost
        self.total_calls = prospective_calls
        self._recent.append(endpoint)


class DataForSEOClient:
    """Thin HTTP wrapper. Auth via HTTP Basic. Cost tracked per call.

    Endpoints used by this project (in order of call frequency):
      - POST /v3/serp/google/organic/live/advanced   (~$0.002/query)
      - POST /v3/keywords_data/google_ads/search_volume/live   (~$0.05/1000 kw)
      - POST /v3/dataforseo_labs/google/bulk_keyword_difficulty/live   (~$0.01/1000 kw)
      - POST /v3/dataforseo_labs/google/keyword_suggestions/live   (~$0.01/task)
      - POST /v3/dataforseo_labs/google/ranked_keywords/live   (~$0.02/task)
      - GET  /v3/appendix/user_data   (free; used for --mode validate)

    Pricing is the spec's Section 4 estimate; verify against the dashboard
    during implementation Step 0 (see plan Task 0 in spec).
    """

    BASE_URL = "https://api.dataforseo.com"

    def __init__(self) -> None:
        if not settings.dataforseo_login or not settings.dataforseo_password:
            raise RuntimeError(
                "DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD must be set in .env"
            )
        self._http = httpx.AsyncClient(
            base_url=self.BASE_URL,
            auth=(settings.dataforseo_login, settings.dataforseo_password),
            timeout=30.0,
        )
        self.tracker = CostTracker(
            max_cost=settings.dataforseo_max_cost_per_run,
            max_calls=settings.dataforseo_max_calls_per_run,
        )

    async def post(self, path: str, *, json_body: Any) -> dict:
        response = await self._http.post(path, json=json_body)
        response.raise_for_status()
        payload = response.json()
        cost = float(payload.get("cost", 0.0))
        self.tracker.record(cost=cost, endpoint=path)
        return payload

    async def get(self, path: str) -> dict:
        response = await self._http.get(path)
        response.raise_for_status()
        payload = response.json()
        cost = float(payload.get("cost", 0.0))
        self.tracker.record(cost=cost, endpoint=path)
        return payload

    async def aclose(self) -> None:
        await self._http.aclose()


_client: Optional[DataForSEOClient] = None


def get_client() -> DataForSEOClient:
    """Return the process-scoped singleton client.

    The CostTracker on the instance is shared across all @tool calls
    in one main.py invocation, so caps apply at the right granularity.
    """
    global _client
    if _client is None:
        _client = DataForSEOClient()
    return _client
```

- [ ] **Step 5: Run the tests to verify pass**

Run: `uv run pytest tests/test_dataforseo_client.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add services/dataforseo_client.py tests/test_dataforseo_client.py tests/fixtures/dfs_serp_response.json
git commit -m "feat: add DataForSEOClient singleton + first SERP fixture

get_client() returns a process-scoped instance. CostTracker is on
the instance so caps apply across one main.py invocation. Cost is
read from the 'cost' field in every DFS response (the same source
the dashboard's billing uses)."
```

---

## Task 8: Add `dfs_serp_live_advanced` @tool

**Why now:** This is the workhorse SEO tool — every keyword candidate gets a SERP check. Worth implementing first so the agent has the most-used tool earliest.

**Files:**
- Create: `tools/dataforseo.py` (just this tool — others added in Tasks 9–10)
- Modify: `tests/test_dataforseo_client.py` (or new `tests/test_dataforseo_tools.py`)

- [ ] **Step 1: Write the failing tool test**

Create `tests/test_dataforseo_tools.py`:

```python
"""@tool wrappers in tools/dataforseo.py."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def test_dfs_serp_live_advanced_returns_formatted_summary():
    from services import dataforseo_client as client_mod
    from tools.dataforseo import dfs_serp_live_advanced

    client_mod._client = None
    payload = _load_fixture("dfs_serp_response.json")

    with patch.object(client_mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = client_mod.get_client()
        client._http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_resp.raise_for_status = MagicMock()
        client._http.post = AsyncMock(return_value=mock_resp)

        result = await dfs_serp_live_advanced.ainvoke({"query": "how to get rid of tutorial hell"})

    assert "reddit.com" in result
    assert "How do you escape tutorial hell?" in result  # PAA question, surfaced
    assert "rank 1" in result.lower() or "#1" in result
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_dataforseo_tools.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the tool**

Create `tools/dataforseo.py`:

```python
"""DataForSEO @tool wrappers for the SEO agent.

The DFS API returns sprawling JSON; each wrapper normalizes one call into
a compact string the LLM agent can reason over. Compact > complete here —
the SEO agent's job is selection, not analysis of raw JSON.

Tools added across Tasks 8-10:
  - dfs_serp_live_advanced       (this task)
  - dfs_keyword_suggestions      (Task 9)
  - dfs_bulk_keyword_data        (Task 10)

The DFS Labs ranked-keywords-for-site call lives in
services/dataforseo_client.py (not wrapped as @tool) because it's only
called from measurement_agent — see Task 30.
"""

from langchain_core.tools import tool

from services.dataforseo_client import get_client


@tool
async def dfs_serp_live_advanced(query: str) -> str:
    """Fetch Google SERP for one query. Returns top organic results + People Also Ask.

    Use for SERP inspection: who's ranking, how strong/weak, what content type.
    One call per shortlisted keyword candidate.
    """
    client = get_client()
    payload = await client.post(
        "/v3/serp/google/organic/live/advanced",
        json_body=[{
            "keyword": query,
            "location_code": 2840,   # United States
            "language_code": "en",
            "depth": 10,
        }],
    )

    try:
        result = payload["tasks"][0]["result"][0]
    except (KeyError, IndexError):
        return f"No SERP result for {query!r}."

    lines = [f"SERP for {query!r}:"]
    paa_questions: list[str] = []

    for item in result.get("items", []):
        kind = item.get("type")
        if kind == "organic":
            rank = item.get("rank_absolute", "?")
            domain = item.get("domain", "")
            title = item.get("title", "")
            lines.append(f"  #{rank} {domain} — {title}")
        elif kind == "people_also_ask_element":
            for paa in item.get("items", []):
                q = paa.get("title", "").strip()
                if q:
                    paa_questions.append(q)

    if paa_questions:
        lines.append("")
        lines.append("People Also Ask:")
        for q in paa_questions[:5]:
            lines.append(f"  - {q}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_dataforseo_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/dataforseo.py tests/test_dataforseo_tools.py
git commit -m "feat: add dfs_serp_live_advanced @tool

One call returns SERP + PAA + related searches. Replaces the
tavily-as-SERP + SerpAPI-PAA combo used previously."
```

---

## Task 9: Add `dfs_keyword_suggestions` @tool

**Files:**
- Modify: `tools/dataforseo.py`
- Modify: `tests/test_dataforseo_tools.py`
- Create: `tests/fixtures/dfs_keyword_suggestions_response.json`

- [ ] **Step 1: Create fixture**

Create `tests/fixtures/dfs_keyword_suggestions_response.json`:

```json
{
  "version": "0.1.20240101",
  "status_code": 20000,
  "status_message": "Ok.",
  "cost": 0.01,
  "tasks": [
    {
      "id": "task-id-2",
      "status_code": 20000,
      "result": [
        {
          "seed_keyword": "tutorial hell",
          "items_count": 3,
          "items": [
            {"keyword": "tutorial hell programming", "search_volume": 480, "keyword_difficulty": 22},
            {"keyword": "how to escape tutorial hell", "search_volume": 320, "keyword_difficulty": 18},
            {"keyword": "tutorial hell reddit", "search_volume": 90, "keyword_difficulty": 12}
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_dataforseo_tools.py`:

```python
async def test_dfs_keyword_suggestions_returns_compact_list():
    from services import dataforseo_client as client_mod
    from tools.dataforseo import dfs_keyword_suggestions

    client_mod._client = None
    payload = _load_fixture("dfs_keyword_suggestions_response.json")

    with patch.object(client_mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = client_mod.get_client()
        client._http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_resp.raise_for_status = MagicMock()
        client._http.post = AsyncMock(return_value=mock_resp)

        result = await dfs_keyword_suggestions.ainvoke({"seed": "tutorial hell"})

    assert "tutorial hell programming" in result
    assert "480" in result   # search volume
    assert "22" in result    # difficulty
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_dataforseo_tools.py::test_dfs_keyword_suggestions_returns_compact_list -v`
Expected: FAIL.

- [ ] **Step 4: Implement the tool**

Append to `tools/dataforseo.py`:

```python
@tool
async def dfs_keyword_suggestions(seed: str) -> str:
    """Return long-tail keyword variants for a seed. Includes volume + difficulty.

    Use once per content opportunity during candidate generation to surface
    PAA-style phrasings the seed itself doesn't capture.
    """
    client = get_client()
    payload = await client.post(
        "/v3/dataforseo_labs/google/keyword_suggestions/live",
        json_body=[{
            "keyword": seed,
            "location_code": 2840,
            "language_code": "en",
            "limit": 20,
        }],
    )

    try:
        items = payload["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError):
        return f"No keyword suggestions for {seed!r}."

    lines = [f"Keyword suggestions for {seed!r} (top {min(len(items), 20)}):"]
    for item in items[:20]:
        kw = item.get("keyword", "")
        vol = item.get("search_volume", "—")
        diff = item.get("keyword_difficulty", "—")
        lines.append(f"  - {kw} (volume {vol}, difficulty {diff})")
    return "\n".join(lines)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_dataforseo_tools.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/dataforseo.py tests/test_dataforseo_tools.py tests/fixtures/dfs_keyword_suggestions_response.json
git commit -m "feat: add dfs_keyword_suggestions @tool"
```

---

## Task 10: Add `dfs_bulk_keyword_data` @tool (wraps volume + difficulty endpoints)

**Why one tool, two endpoints:** They're always called together — both are bulk endpoints that take a list of keywords, and the SEO agent reasons over both numbers per keyword. Merging server-side responses into one tool output keeps the agent's mental model simple.

**Files:**
- Modify: `tools/dataforseo.py`
- Modify: `tests/test_dataforseo_tools.py`
- Create: `tests/fixtures/dfs_search_volume_response.json`
- Create: `tests/fixtures/dfs_keyword_difficulty_response.json`

- [ ] **Step 1: Create the two fixtures**

`tests/fixtures/dfs_search_volume_response.json`:

```json
{
  "version": "0.1.20240101",
  "status_code": 20000,
  "cost": 0.0001,
  "tasks": [
    {
      "id": "task-id-3",
      "status_code": 20000,
      "result": [
        {"keyword": "tutorial hell", "search_volume": 880, "competition": 0.12, "cpc": 0.43},
        {"keyword": "how to get rid of tutorial hell", "search_volume": 260, "competition": 0.05, "cpc": 0.21}
      ]
    }
  ]
}
```

`tests/fixtures/dfs_keyword_difficulty_response.json`:

```json
{
  "version": "0.1.20240101",
  "status_code": 20000,
  "cost": 0.0001,
  "tasks": [
    {
      "id": "task-id-4",
      "status_code": 20000,
      "result": [
        {
          "items": [
            {"keyword": "tutorial hell", "keyword_difficulty": 28},
            {"keyword": "how to get rid of tutorial hell", "keyword_difficulty": 19}
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_dataforseo_tools.py`:

```python
async def test_dfs_bulk_keyword_data_merges_volume_and_difficulty():
    from services import dataforseo_client as client_mod
    from tools.dataforseo import dfs_bulk_keyword_data

    client_mod._client = None
    vol_payload = _load_fixture("dfs_search_volume_response.json")
    diff_payload = _load_fixture("dfs_keyword_difficulty_response.json")

    with patch.object(client_mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = client_mod.get_client()
        client._http = MagicMock()

        # First POST call returns volume, second returns difficulty.
        responses = [vol_payload, diff_payload]

        async def fake_post(path, json):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=responses.pop(0))
            return resp

        client._http.post = AsyncMock(side_effect=fake_post)

        result = await dfs_bulk_keyword_data.ainvoke({
            "keywords": ["tutorial hell", "how to get rid of tutorial hell"]
        })

    assert "tutorial hell" in result
    assert "880" in result        # volume
    assert "28" in result         # difficulty
    assert "how to get rid of tutorial hell" in result
    assert "19" in result
    # Two API calls counted in cost tracker.
    assert client.tracker.total_calls == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_dataforseo_tools.py::test_dfs_bulk_keyword_data_merges_volume_and_difficulty -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement the tool**

Append to `tools/dataforseo.py`:

```python
@tool
async def dfs_bulk_keyword_data(keywords: list[str]) -> str:
    """Get monthly search volume + keyword difficulty for a batch of keywords.

    Wraps two DFS endpoints (Google Ads Search Volume + Labs Bulk Keyword
    Difficulty) and merges results on the keyword string. Use once per
    candidate batch (post-filtering) to identify obviously bad bets.
    """
    if not keywords:
        return "No keywords provided."

    client = get_client()

    # Endpoint 1: search volume.
    vol_payload = await client.post(
        "/v3/keywords_data/google_ads/search_volume/live",
        json_body=[{
            "keywords": keywords,
            "location_code": 2840,
            "language_code": "en",
        }],
    )

    # Endpoint 2: keyword difficulty.
    diff_payload = await client.post(
        "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live",
        json_body=[{
            "keywords": keywords,
            "location_code": 2840,
            "language_code": "en",
        }],
    )

    # Build per-keyword dictionaries.
    volume_by_kw: dict[str, dict] = {}
    try:
        for row in vol_payload["tasks"][0]["result"]:
            volume_by_kw[row["keyword"]] = row
    except (KeyError, IndexError, TypeError):
        pass

    difficulty_by_kw: dict[str, int | None] = {}
    try:
        items = diff_payload["tasks"][0]["result"][0]["items"]
        for row in items:
            difficulty_by_kw[row["keyword"]] = row.get("keyword_difficulty")
    except (KeyError, IndexError, TypeError):
        pass

    lines = [f"Bulk data for {len(keywords)} keywords:"]
    for kw in keywords:
        vol_row = volume_by_kw.get(kw, {})
        vol = vol_row.get("search_volume", "—")
        cpc = vol_row.get("cpc", "—")
        comp = vol_row.get("competition", "—")
        diff = difficulty_by_kw.get(kw, "—")
        lines.append(
            f"  - {kw}: volume={vol}, difficulty={diff}, cpc={cpc}, competition={comp}"
        )
    return "\n".join(lines)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_dataforseo_tools.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/dataforseo.py tests/test_dataforseo_tools.py tests/fixtures/dfs_search_volume_response.json tests/fixtures/dfs_keyword_difficulty_response.json
git commit -m "feat: add dfs_bulk_keyword_data @tool (volume + difficulty merge)

Two endpoints, one tool. Volume comes from Google Ads endpoint;
difficulty from DFS Labs. Merged client-side on the keyword string."
```

---

## Task 11: Add `ranked_keywords_for_site` client method (NOT a @tool)

**Why not a @tool:** This is called only by `measurement_agent`. Exposing it to the SEO agent would invite the agent to burn budget on a query that only makes sense in the measurement loop. Living in `services/dataforseo_client.py` (not `tools/dataforseo.py`) makes it invisible to LangChain agent discovery.

**Files:**
- Modify: `services/dataforseo_client.py`
- Modify: `tests/test_dataforseo_client.py`
- Create: `tests/fixtures/dfs_ranked_keywords_response.json`

- [ ] **Step 1: Create the fixture**

`tests/fixtures/dfs_ranked_keywords_response.json`:

```json
{
  "version": "0.1.20240101",
  "status_code": 20000,
  "cost": 0.02,
  "tasks": [
    {
      "id": "task-id-5",
      "status_code": 20000,
      "result": [
        {
          "target": "draftandarc.com",
          "total_count": 3,
          "items": [
            {
              "keyword_data": {"keyword": "tutorial hell python", "search_volume": 90},
              "ranked_serp_element": {"rank_absolute": 28, "url": "https://www.draftandarc.com/blog/tutorial-hell-progress"}
            },
            {
              "keyword_data": {"keyword": "how to escape tutorial hell", "search_volume": 320},
              "ranked_serp_element": {"rank_absolute": 41, "url": "https://www.draftandarc.com/blog/tutorial-hell-progress"}
            },
            {
              "keyword_data": {"keyword": "course platform", "search_volume": 1200},
              "ranked_serp_element": {"rank_absolute": 87, "url": "https://www.draftandarc.com/"}
            }
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_dataforseo_client.py`:

```python
async def test_ranked_keywords_for_site_filters_to_blog_urls():
    from services import dataforseo_client as mod
    mod._client = None
    payload = _load_fixture("dfs_ranked_keywords_response.json")

    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = mod.get_client()
        client._http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_resp.raise_for_status = MagicMock()
        client._http.post = AsyncMock(return_value=mock_resp)

        rows = await client.ranked_keywords_for_site("draftandarc.com", url_substring="/blog/")

    # Only blog URLs come back; the homepage row is filtered out.
    assert len(rows) == 2
    keywords = {r["keyword"] for r in rows}
    assert "tutorial hell python" in keywords
    assert "course platform" not in keywords  # filtered (homepage URL)
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_dataforseo_client.py::test_ranked_keywords_for_site_filters_to_blog_urls -v`
Expected: FAIL with `AttributeError`.

- [ ] **Step 4: Implement the method**

Append to `services/dataforseo_client.py` (inside the `DataForSEOClient` class, after `aclose`):

```python
    async def ranked_keywords_for_site(
        self,
        target: str,
        *,
        url_substring: str = "",
        limit: int = 1000,
    ) -> list[dict]:
        """All keywords the target domain currently ranks for.

        Returns a list of dicts with keys: keyword, position, search_volume, url.
        If `url_substring` is given, filters to ranked URLs containing it
        (we use "/blog/" because the DFS endpoint takes a domain target, not
        a path prefix — see spec Section 6).
        """
        payload = await self.post(
            "/v3/dataforseo_labs/google/ranked_keywords/live",
            json_body=[{
                "target": target,
                "location_code": 2840,
                "language_code": "en",
                "limit": limit,
            }],
        )

        rows: list[dict] = []
        try:
            items = payload["tasks"][0]["result"][0]["items"]
        except (KeyError, IndexError, TypeError):
            return rows

        for item in items:
            kd = item.get("keyword_data") or {}
            rse = item.get("ranked_serp_element") or {}
            url = rse.get("url", "")
            if url_substring and url_substring not in url:
                continue
            rows.append({
                "keyword": kd.get("keyword", ""),
                "position": rse.get("rank_absolute", 0),
                "search_volume": kd.get("search_volume", 0),
                "url": url,
            })
        return rows
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_dataforseo_client.py -v`
Expected: all PASS.

- [ ] **Step 6: Verify the method is NOT importable from `tools.dataforseo`**

Run: `uv run python -c "from tools.dataforseo import ranked_keywords_for_site"`
Expected: `ImportError`. (This is the whole point — the SEO agent can't accidentally call it.)

- [ ] **Step 7: Commit**

```bash
git add services/dataforseo_client.py tests/test_dataforseo_client.py tests/fixtures/dfs_ranked_keywords_response.json
git commit -m "feat: add ranked_keywords_for_site method (not exposed as @tool)

DFS endpoint takes a domain target; we filter to /blog/ URLs
client-side. Used only by measurement_agent — kept off the
SEO agent's tool list so the agent can't burn budget on it."
```

---

## Task 12: Add `--mode validate` for DataForSEO

**Why now:** Before swapping the SEO agent's tool list (Task 14), it's wise to confirm DataForSEO auth works in your environment. The validate mode is also extended in Task 20 for GSC + GA4.

**Files:**
- Modify: `services/dataforseo_client.py` (add `validate()` method)
- Modify: `agents/orchestrator.py` (add `run_validate()`)
- Modify: `main.py` (add `--mode validate`)
- Modify: `tests/test_dataforseo_client.py`

- [ ] **Step 1: Write the failing test for `validate()`**

Append to `tests/test_dataforseo_client.py`:

```python
async def test_validate_calls_user_data_endpoint():
    from services import dataforseo_client as mod
    mod._client = None

    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "u"
        mock_settings.dataforseo_password = "p"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = mod.get_client()
        client._http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value={
            "status_code": 20000,
            "cost": 0.0,
            "tasks": [{"result": [{"login": "u", "balance": 50.00}]}],
        })
        mock_resp.raise_for_status = MagicMock()
        client._http.get = AsyncMock(return_value=mock_resp)

        ok, message = await client.validate()

    assert ok is True
    assert "50.00" in message or "50.0" in message
    client._http.get.assert_called_once_with("/v3/appendix/user_data")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_dataforseo_client.py::test_validate_calls_user_data_endpoint -v`
Expected: FAIL with `AttributeError: 'DataForSEOClient' object has no attribute 'validate'`.

- [ ] **Step 3: Implement `validate()` on the client**

Append to `services/dataforseo_client.py` inside `DataForSEOClient`:

```python
    async def validate(self) -> tuple[bool, str]:
        """Cheap auth check via /v3/appendix/user_data (free endpoint).

        Returns (ok, message). On success the message includes account balance.
        On failure the message describes the auth or HTTP problem.
        """
        try:
            payload = await self.get("/v3/appendix/user_data")
        except httpx.HTTPStatusError as exc:
            return False, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Request failed: {exc}"

        try:
            info = payload["tasks"][0]["result"][0]
            balance = info.get("balance", "unknown")
            login = info.get("login", "unknown")
            return True, f"DataForSEO ok. Account: {login}. Balance: ${balance}"
        except (KeyError, IndexError, TypeError):
            return False, f"Unexpected response shape: {payload}"
```

- [ ] **Step 4: Add `run_validate` to the orchestrator**

Open `agents/orchestrator.py`. Add at the bottom:

```python
async def run_validate() -> int:
    """Cheap end-to-end validation of external integrations.

    GSC + GA4 checks are added in Task 19. For now, only DataForSEO is checked.
    Returns 0 on full success, 1 if any check failed.

    Each check is independent and degrades gracefully — a missing credential
    must produce a clean [FAIL] line, not a Python traceback. That's the
    entire point of validate mode.
    """
    from services.dataforseo_client import get_client, DataForSEOClient

    results: list[tuple[str, bool, str]] = []

    dfs_client: DataForSEOClient | None = None
    try:
        dfs_client = get_client()
        ok, message = await dfs_client.validate()
    except Exception as exc:  # noqa: BLE001
        # Covers RuntimeError on missing credentials and any other init failure.
        ok, message = False, f"Could not construct client: {exc}"
    finally:
        if dfs_client is not None:
            try:
                await dfs_client.aclose()
            except Exception:  # noqa: BLE001
                pass  # Cleanup failure shouldn't mask the real error.
    results.append(("DataForSEO", ok, message))

    all_ok = True
    for name, ok, message in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {message}")
        if not ok:
            all_ok = False

    return 0 if all_ok else 1
```

- [ ] **Step 5: Wire `--mode validate` into `main.py`**

Open `main.py`. Update the parser choices and add a handler:

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft and Arc marketing agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py --mode setup       First-time setup
  uv run python main.py --mode weekly      Plan 4 articles
  uv run python main.py --mode article     Write the next planned article
  uv run python main.py --mode validate    Check external API auth
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["setup", "weekly", "article", "validate"],
        required=True,
        help="setup | weekly | article | validate",
    )
    return parser


async def _run_validate() -> None:
    from agents.orchestrator import run_validate
    import sys
    exit_code = await run_validate()
    sys.exit(exit_code)
```

In the `main()` dispatch, add:

```python
    elif args.mode == "validate":
        asyncio.run(_run_validate())
```

- [ ] **Step 6: Add the missing-credentials test**

Append to `tests/test_dataforseo_client.py`:

```python
async def test_run_validate_handles_missing_credentials_cleanly(capsys):
    """The exact case validate exists to diagnose: empty .env must produce
    [FAIL] DataForSEO: ... not a traceback."""
    from agents.orchestrator import run_validate
    from services import dataforseo_client as mod

    mod._client = None
    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = ""
        mock_settings.dataforseo_password = ""
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        exit_code = await run_validate()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[FAIL] DataForSEO" in captured.out
    assert "must be set" in captured.out.lower() or "could not construct" in captured.out.lower()
```

- [ ] **Step 7: Run the test suite**

Run: `uv run pytest tests/test_dataforseo_client.py -v`
Expected: all PASS, including the new missing-credentials test.

- [ ] **Step 8: Smoke-test the validate command**

If you have real DFS credentials set up:
```bash
uv run python main.py --mode validate
```
Expected: prints `[PASS] DataForSEO: ... Balance: $...`. Without credentials, it should print `[FAIL] DataForSEO: Could not construct client: ...` (and exit code 1) — never a traceback.

- [ ] **Step 9: Commit**

```bash
git add services/dataforseo_client.py agents/orchestrator.py main.py tests/test_dataforseo_client.py
git commit -m "feat: add --mode validate for DataForSEO

Calls free /v3/appendix/user_data endpoint. Wraps get_client() in
try/except so missing credentials produce a clean [FAIL] line, not
a traceback. Closes the httpx AsyncClient in a finally block.
Exit code 0 on success, 1 on any failure. GSC + GA4 added in Task 19."
```

---

## Task 13: Add `seo_coverage_note` field to `SEOOutput`

**Why now:** Task 14 (SEO agent tool swap) introduces the budget try/except that needs somewhere to write the partial-data note. Adding the field before changing the agent avoids a cross-cutting refactor.

**Files:**
- Modify: `output_schemas.py`
- Modify: `prompts/md/chains/seo_synthesis.md`

- [ ] **Step 1: Add the field to `SEOOutput`**

Open `output_schemas.py`. Find the `SEOOutput` class and update:

```python
class SEOOutput(_StrictModel):
    articles: list[ArticlePlanOutput]
    seo_coverage_note: str = ""   # NEW: populated when DataForSEOBudgetExceeded
                                  # fired mid-batch and synthesis ran on partial
                                  # data. Empty string when the batch completed
                                  # normally.
```

- [ ] **Step 2: Update the synthesis prompt to set the note**

Open `prompts/md/chains/seo_synthesis.md`. Add a section before the `---HUMAN---` separator:

```markdown
# DATA COVERAGE NOTE

The RAW KEYWORD AND SERP DATA below may include a note like
"budget cap reached after N keyword evaluations — synthesis ran on
partial data". When you see that note:

- Set `seo_coverage_note` in your output to a one-sentence explanation
  including N and what's likely missing (e.g., "Budget cap reached after 5
  evaluations; SERP data for 3 opportunities was incomplete — verdicts are
  best-effort.").
- Still produce as many article plans as the partial data supports. Fewer
  than 4 is fine if you genuinely can't justify them; do not invent rationale.

When no such note appears, leave `seo_coverage_note` as an empty string.
```

- [ ] **Step 3: Confirm the schema parses**

Run: `uv run python -c "from output_schemas import SEOOutput; print(SEOOutput(articles=[]).seo_coverage_note)"`
Expected: prints `` (empty string).

- [ ] **Step 4: Commit**

```bash
git add output_schemas.py prompts/md/chains/seo_synthesis.md
git commit -m "feat: add seo_coverage_note to SEOOutput

Populated by the synthesis LLM when raw data flags a budget cap.
Wired into the SEO agent's try/except in Task 14."
```

---

## Task 14: Swap SEO agent tool list + add budget try/except

**Why now:** All DataForSEO tools (8–10) exist; the SEOOutput schema (13) is ready. Now the SEO agent can switch sources.

**Files:**
- Modify: `agents/seo_agent.py`
- Modify: `prompts/md/agents/seo_system.md` (TOOLS section)
- Create: `tests/test_seo_agent_budget.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_seo_agent_budget.py`:

```python
"""SEO agent's behaviour when DataForSEOBudgetExceeded fires mid-batch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_run_seo_agent_falls_through_on_budget_exceeded():
    """When the @tool raises DataForSEOBudgetExceeded, the agent should NOT crash.
    Instead it should run synthesis on the partial data and set seo_coverage_note."""
    from agents import seo_agent
    from services.dataforseo_client import DataForSEOBudgetExceeded
    from output_schemas import SEOOutput, ArticlePlanOutput

    fake_messages_result = {
        "messages": [
            MagicMock(content="some partial gathered data before the cap fired")
        ]
    }

    # The agent ainvoke raises midway.
    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(
        side_effect=DataForSEOBudgetExceeded("cost cap")
    )

    fake_output = SEOOutput(
        articles=[],
        seo_coverage_note="Budget cap reached; synthesis ran on partial data."
    )
    fake_chain = MagicMock()
    fake_chain.ainvoke = AsyncMock(return_value=fake_output)

    with patch.object(seo_agent, "create_agent", return_value=fake_agent), \
         patch.object(seo_agent, "get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = fake_chain
        mock_get_llm.return_value = mock_llm

        result = await seo_agent.run_seo_agent("research brief", existing_ids=set())

    assert result == []  # No articles produced (consistent with empty SEOOutput).
    # The synthesis chain WAS called (i.e. we did not crash on the cap).
    fake_chain.ainvoke.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_seo_agent_budget.py -v`
Expected: FAIL (current `run_seo_agent` does not catch the exception).

- [ ] **Step 3: Update `agents/seo_agent.py`**

Replace the imports and `run_seo_agent` body:

```python
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from models.article import ArticleType, ContentCalendarEntry
from output_schemas import SEOOutput
from prompts.loader import load_prompt, load_system_prompt
from services.dataforseo_client import DataForSEOBudgetExceeded
from services.llm import get_llm
from tools.dataforseo import (
    dfs_serp_live_advanced,
    dfs_keyword_suggestions,
    dfs_bulk_keyword_data,
)


SEO_AGENT_SYSTEM_PROMPT = load_system_prompt("agents/seo_system.md")
SEO_KICKOFF = (
    "Research keywords and SERP data for 4 article ideas based on the context "
    "provided. Avoid these existing topics: {existing_ids}. Use DataForSEO to "
    "validate each idea."
)
seo_synthesis_prompt = load_prompt("chains/seo_synthesis.md")


def _to_calendar_entry(plan) -> ContentCalendarEntry:
    return ContentCalendarEntry(
        id=plan.id,
        title=plan.title,
        primary_keyword=plan.primary_keyword,
        secondary_keywords=plan.secondary_keywords,
        search_intent=plan.search_intent,
        article_type=ArticleType(plan.article_type),
        target_audience=plan.target_audience,
        angle=plan.angle,
        meta_description=plan.meta_description,
        suggested_headings=plan.suggested_headings,
        cta_prompt=plan.cta_prompt,
        blog_category=plan.blog_category,   # preserved from upstream auto-PR feature
    )


async def run_seo_agent(research_brief: str, existing_ids: set[str]) -> list[ContentCalendarEntry]:
    """Run the SEO agent. Returns up to 4 new ContentCalendarEntry items.

    If DataForSEOBudgetExceeded fires mid-batch, falls through to synthesis with
    whatever partial data the agent gathered and prompts the synthesis LLM to
    populate seo_coverage_note. Does not crash on budget exhaustion.
    """
    tools = [
        dfs_serp_live_advanced,
        dfs_keyword_suggestions,
        dfs_bulk_keyword_data,
    ]
    agent = create_agent(get_llm(), tools=tools, system_prompt=SEO_AGENT_SYSTEM_PROMPT)

    budget_note = ""
    try:
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=f"{research_brief}\n\n{SEO_KICKOFF.format(existing_ids=existing_ids or 'none')}")]
        })
        gathered_data = result["messages"][-1].content
    except DataForSEOBudgetExceeded as exc:
        gathered_data = (
            f"budget cap reached during tool calls — synthesis ran on partial data. "
            f"Reason: {exc}"
        )
        budget_note = "Budget exceeded mid-batch"

    chain = seo_synthesis_prompt | get_llm().with_structured_output(SEOOutput, method="function_calling")
    output: SEOOutput = await chain.ainvoke({
        "research_brief": research_brief,
        "existing_ids": ", ".join(existing_ids) if existing_ids else "none",
        "gathered_data": gathered_data,
    })

    if budget_note and not output.seo_coverage_note:
        # Belt-and-suspenders: ensure the note is set even if the LLM forgot.
        output.seo_coverage_note = budget_note

    return [_to_calendar_entry(plan) for plan in output.articles]
```

- [ ] **Step 4: Remove the deprecation shims from `tools/__init__.py`**

The SEO agent no longer imports `people_also_ask` or `google_trends` (the file you just wrote uses the DataForSEO tools instead). The shims in `tools/__init__.py` (Task 1) are now dead.

Open `tools/__init__.py`. Delete the entire "Deprecation shims" block at the bottom of the file (the two `@tool`-decorated functions for `people_also_ask` and `google_trends`, plus the comment header that explains them).

Also update `tests/test_tools_package.py`: delete `test_seo_agent_imports_resolve_to_shims` and `test_shims_raise_when_invoked`. Add their replacement:

```python
def test_orphaned_seo_tools_are_gone():
    """people_also_ask and google_trends are removed in Task 14 — they MUST NOT exist."""
    import tools
    assert not hasattr(tools, "people_also_ask")
    assert not hasattr(tools, "google_trends")
```

Run: `uv run pytest tests/test_tools_package.py -v`
Expected: all PASS.

- [ ] **Step 5: Update the TOOLS section of `prompts/md/agents/seo_system.md`**

Open `prompts/md/agents/seo_system.md`. Replace the existing `# TOOLS` section (around lines 13–17 of the current file) with:

```markdown
# TOOLS

- `dfs_serp_live_advanced(query)` — fetch real Google SERP for a query.
  Returns top 10 organic + People Also Ask in one call. Use for SERP
  inspection on shortlisted candidates.
- `dfs_keyword_suggestions(seed)` — long-tail keyword variants for a seed,
  with volume + difficulty. Use ONCE per content opportunity during
  candidate generation to surface PAA-style phrasings.
- `dfs_bulk_keyword_data(keywords)` — monthly search volume + keyword
  difficulty for a batch of keywords. Use AFTER candidate generation to
  filter obviously bad bets (zero volume, difficulty above 50).
```

- [ ] **Step 6: Run the test**

Run: `uv run pytest tests/test_seo_agent_budget.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -x -q`
Expected: PASS (any old test that referenced the removed tools should already have been cleaned in Tasks 1–2).

- [ ] **Step 8: Commit**

```bash
git add agents/seo_agent.py prompts/md/agents/seo_system.md tools/__init__.py tests/test_seo_agent_budget.py tests/test_tools_package.py
git commit -m "feat: switch SEO agent to DataForSEO tools + remove deprecation shims

Tool list is now [dfs_serp_live_advanced, dfs_keyword_suggestions,
dfs_bulk_keyword_data]. The agent caller catches
DataForSEOBudgetExceeded around ainvoke and runs synthesis on
partial data instead of crashing.

Removes the Task 1 deprecation shims for people_also_ask and
google_trends now that nothing imports them.

This is the spec's 'decision point' — run a real weekly batch and
compare output to the last manual one before proceeding."
```

---

## Task 15: Update SEO synthesis prompt to mention DataForSEO metric names

**Why now:** The synthesis LLM has historically read SERP snippets via Tavily. After Task 14 its input is DataForSEO-shaped. Adjust the prompt so it knows what `keyword_difficulty` and `search_volume` mean.

**Files:**
- Modify: `prompts/md/chains/seo_synthesis.md`

- [ ] **Step 1: Update the keyword-selection rules section**

Open `prompts/md/chains/seo_synthesis.md`. Find the `# KEYWORD SELECTION RULES` section and replace the "Reachable competition" bullet:

```markdown
- **Reachable competition:** prefer keywords with DataForSEO `keyword_difficulty`
  under 30. Use the SERP evidence as the deciding tiebreak when difficulty
  is borderline (20–35). If the top 10 results are dominated by domains like
  Wikipedia, Coursera, edX, Khan Academy, NYTimes, or Harvard, skip even if
  difficulty looks low — the agent is interpreting "reachable" as page-2 reachable.
- **Stable or rising trend:** trend data is no longer available (pytrends was
  removed). Use `search_volume` as a proxy: a keyword with volume that's been
  consistent month-over-month is a safer pick than one whose volume halved.
  Do not invent trend direction.
```

- [ ] **Step 2: Confirm the prompt loads**

Run: `uv run python -c "from prompts.loader import load_prompt; load_prompt('chains/seo_synthesis.md'); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add prompts/md/chains/seo_synthesis.md
git commit -m "docs: update SEO synthesis prompt for DataForSEO metric names

keyword_difficulty and search_volume are the new authoritative signals.
Trend direction is dropped — pytrends is gone."
```

---

## Task 16: Add Google service-account config + dependencies

**Why now:** Tasks 17 (GSC) and 18 (GA4) both need `google-auth` and the GOOGLE_APPLICATION_CREDENTIALS variable. Adding the deps once before either client.

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add settings**

Open `config.py`. Add fields inside `Settings`:

```python
    # Google measurement APIs (GSC + GA4)
    google_application_credentials: str = ""
    gsc_site_url: str = "sc-domain:draftandarc.com"
    ga4_property_id: str = ""
```

- [ ] **Step 2: Uncomment the Google block in `.env.example`**

Open `.env.example`. Remove the leading `#` from the three Google lines:

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/Users/ilirgruda/.config/draftandarc/gcp-service-account.json
GSC_SITE_URL=sc-domain:draftandarc.com
GA4_PROPERTY_ID=123456789
```

- [ ] **Step 3: Add deps to `pyproject.toml`**

In `[project] dependencies`:

```toml
    "google-auth>=2.0",
    "google-api-python-client>=2.0",
    "google-analytics-data>=0.18",
    "jinja2>=3.0",
```

- [ ] **Step 4: Sync**

Run: `uv sync`
Expected: deps installed.

- [ ] **Step 5: Confirm settings parse**

Run: `uv run python -c "from config import settings; print(settings.gsc_site_url, repr(settings.ga4_property_id))"`
Expected: `sc-domain:draftandarc.com ''` (or with values if you populated `.env` already).

- [ ] **Step 6: Commit**

```bash
git add config.py .env.example pyproject.toml uv.lock
git commit -m "feat: add Google service-account settings + measurement deps"
```

---

## Task 17: Implement `services/gsc_client.py` (sync internals, async public API)

**Files:**
- Create: `services/gsc_client.py`
- Create: `tests/test_gsc_client.py`
- Create: `tests/fixtures/gsc_search_analytics_response.json`

- [ ] **Step 1: Create the fixture**

`tests/fixtures/gsc_search_analytics_response.json`:

```json
{
  "rows": [
    {
      "keys": ["https://www.draftandarc.com/blog/tutorial-hell-progress", "how to get rid of tutorial hell"],
      "clicks": 8,
      "impressions": 142,
      "ctr": 0.0563,
      "position": 9.2
    },
    {
      "keys": ["https://www.draftandarc.com/blog/tutorial-hell-progress", "stop watching tutorials"],
      "clicks": 3,
      "impressions": 89,
      "ctr": 0.0337,
      "position": 14.1
    },
    {
      "keys": ["https://www.draftandarc.com/blog/anki-review-queue-burnout", "anki backlog"],
      "clicks": 0,
      "impressions": 5,
      "ctr": 0.0,
      "position": 41.0
    }
  ],
  "responseAggregationType": "byPage"
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_gsc_client.py`:

```python
"""GSC client tests. Mocks googleapiclient.discovery.build."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def test_query_blog_performance_returns_typed_rows():
    from services import gsc_client

    response = _load_fixture("gsc_search_analytics_response.json")

    mock_service = MagicMock()
    mock_service.searchanalytics().query().execute.return_value = response

    with patch.object(gsc_client, "_build_service", return_value=mock_service), \
         patch.object(gsc_client, "settings") as mock_settings:
        mock_settings.gsc_site_url = "sc-domain:draftandarc.com"
        mock_settings.google_application_credentials = "/tmp/fake.json"

        rows = await gsc_client.query_blog_performance(
            start_date=date(2026, 4, 21),
            end_date=date(2026, 5, 19),
        )

    assert len(rows) == 3
    assert rows[0]["page"] == "https://www.draftandarc.com/blog/tutorial-hell-progress"
    assert rows[0]["query"] == "how to get rid of tutorial hell"
    assert rows[0]["clicks"] == 8
    assert rows[0]["impressions"] == 142
    assert rows[0]["position"] == 9.2


async def test_query_blog_performance_handles_empty_response():
    from services import gsc_client

    mock_service = MagicMock()
    mock_service.searchanalytics().query().execute.return_value = {}  # no 'rows'

    with patch.object(gsc_client, "_build_service", return_value=mock_service), \
         patch.object(gsc_client, "settings") as mock_settings:
        mock_settings.gsc_site_url = "sc-domain:draftandarc.com"
        mock_settings.google_application_credentials = "/tmp/fake.json"

        rows = await gsc_client.query_blog_performance(
            start_date=date(2026, 4, 21),
            end_date=date(2026, 5, 19),
        )

    assert rows == []
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_gsc_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.gsc_client'`.

- [ ] **Step 4: Implement the GSC client**

Create `services/gsc_client.py`:

```python
"""Google Search Console client.

google-api-python-client is sync-only. The public query_* methods are async
and wrap their sync helpers in asyncio.to_thread so the call doesn't block
the event loop.
"""

import asyncio
from datetime import date
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import settings


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _build_service():
    """Build a Search Console service client using the service-account credentials."""
    if not settings.google_application_credentials:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS must be set in .env")

    creds = service_account.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=SCOPES,
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


async def query_blog_performance(start_date: date, end_date: date) -> list[dict[str, Any]]:
    """Per-(page, query) performance over the window, filtered to /blog/ URLs.

    Returns rows with keys: page, query, clicks, impressions, ctr, position.

    Uses dataState='final' so the last ~2-3 days of unfinalized data are
    excluded. Callers should reflect this in the effective window header
    (start_date, end_date - 3 days) in user-facing output.
    """
    return await asyncio.to_thread(_query_blog_performance_sync, start_date, end_date)


def _query_blog_performance_sync(start_date: date, end_date: date) -> list[dict[str, Any]]:
    service = _build_service()
    request_body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page", "query"],
        "dimensionFilterGroups": [{
            "filters": [{
                "dimension": "page",
                "operator": "contains",
                "expression": "/blog/",
            }]
        }],
        "rowLimit": 25000,
        "dataState": "final",
    }
    response = service.searchanalytics().query(
        siteUrl=settings.gsc_site_url,
        body=request_body,
    ).execute()

    rows = []
    for row in response.get("rows", []):
        keys = row.get("keys", ["", ""])
        rows.append({
            "page": keys[0] if len(keys) > 0 else "",
            "query": keys[1] if len(keys) > 1 else "",
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0.0),
            "position": row.get("position", 0.0),
        })
    return rows


async def validate() -> tuple[bool, str]:
    """Cheap check: list sites the service account can see. Free, no quota cost."""
    try:
        return await asyncio.to_thread(_validate_sync)
    except Exception as exc:  # noqa: BLE001
        return False, f"GSC validate failed: {exc}"


def _validate_sync() -> tuple[bool, str]:
    service = _build_service()
    response = service.sites().list().execute()
    sites = [s.get("siteUrl", "") for s in response.get("siteEntry", [])]
    if not sites:
        return False, "Service account has no GSC properties — check permission grant."
    if settings.gsc_site_url not in sites:
        return False, (
            f"GSC_SITE_URL={settings.gsc_site_url!r} not in accessible properties: {sites}"
        )
    return True, f"GSC ok. Accessible properties: {sites}"
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_gsc_client.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/gsc_client.py tests/test_gsc_client.py tests/fixtures/gsc_search_analytics_response.json
git commit -m "feat: add Google Search Console client

Sync internals (google-api-python-client is sync-only) wrapped in
asyncio.to_thread for the public async API. dataState='final' so
the last 2-3 days of partial data are excluded."
```

---

## Task 18: Implement `services/ga4_client.py` (two-report merge)

**Why two reports:** GA4's `runReport` cannot filter one metric to one event while leaving other metrics unfiltered. A `dimensionFilter` on `eventName` would scope `activeUsers` / `engagedSessions` / `averageSessionDuration` to only sessions that fired `signup_cta_click`, making engagement metrics meaningless. So we run two reports and merge client-side on `pagePath`. The `BetaAnalyticsDataAsyncClient` is fully async — no `asyncio.to_thread` wrap needed.

**Files:**
- Create: `services/ga4_client.py`
- Create: `tests/test_ga4_client.py`
- Create: `tests/fixtures/ga4_engagement_response.json`
- Create: `tests/fixtures/ga4_conversion_response.json`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/ga4_engagement_response.json`:

```json
{
  "rows": [
    {
      "dimensionValues": [{"value": "/blog/tutorial-hell-progress"}, {"value": "google / organic"}],
      "metricValues": [{"value": "24"}, {"value": "18"}, {"value": "102.5"}]
    },
    {
      "dimensionValues": [{"value": "/blog/tutorial-hell-progress"}, {"value": "twitter / referral"}],
      "metricValues": [{"value": "3"}, {"value": "2"}, {"value": "45.0"}]
    },
    {
      "dimensionValues": [{"value": "/blog/anki-review-queue-burnout"}, {"value": "(direct) / (none)"}],
      "metricValues": [{"value": "1"}, {"value": "0"}, {"value": "8.0"}]
    }
  ]
}
```

`tests/fixtures/ga4_conversion_response.json`:

```json
{
  "rows": [
    {
      "dimensionValues": [{"value": "/blog/tutorial-hell-progress"}, {"value": "signup_cta_click"}],
      "metricValues": [{"value": "2"}]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_ga4_client.py`:

```python
"""GA4 client tests. Mocks BetaAnalyticsDataAsyncClient.run_report."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _build_mock_response(fixture_name: str):
    """Build a mock RunReportResponse-shaped object from a fixture."""
    payload = _load_fixture(fixture_name)
    resp = MagicMock()
    rows = []
    for raw_row in payload["rows"]:
        row = MagicMock()
        row.dimension_values = [MagicMock(value=dv["value"]) for dv in raw_row["dimensionValues"]]
        row.metric_values = [MagicMock(value=mv["value"]) for mv in raw_row["metricValues"]]
        rows.append(row)
    resp.rows = rows
    return resp


async def test_query_blog_engagement_returns_rows_and_cta_separately():
    """GA4 client returns a (rows, cta_clicks_by_path) tuple. The separation
    means downstream code doesn't have to do a fragile divide-by-row-count
    trick to dedupe per-path CTA counts across multiple source/medium splits."""
    from services import ga4_client

    eng = _build_mock_response("ga4_engagement_response.json")
    conv = _build_mock_response("ga4_conversion_response.json")

    mock_async_client = MagicMock()
    mock_async_client.run_report = AsyncMock(side_effect=[eng, conv])

    with patch.object(ga4_client, "_build_async_client", return_value=mock_async_client), \
         patch.object(ga4_client, "settings") as mock_settings:
        mock_settings.ga4_property_id = "123456789"
        mock_settings.google_application_credentials = "/tmp/fake.json"

        rows, cta_by_path = await ga4_client.query_blog_engagement(
            start_date=date(2026, 4, 21),
            end_date=date(2026, 5, 19),
        )

    # Engagement rows for tutorial-hell-progress (2 source/medium splits).
    by_key = {(r["page_path"], r["source_medium"]): r for r in rows}

    organic = by_key[("/blog/tutorial-hell-progress", "google / organic")]
    assert organic["active_users"] == 24
    assert organic["engaged_sessions"] == 18
    assert organic["avg_session_duration"] == 102.5

    twitter = by_key[("/blog/tutorial-hell-progress", "twitter / referral")]
    assert twitter["active_users"] == 3

    anki = by_key[("/blog/anki-review-queue-burnout", "(direct) / (none)")]
    assert anki["active_users"] == 1

    # CTA attribution is per-path, not per-split. Returned as a dict.
    assert cta_by_path == {"/blog/tutorial-hell-progress": 2}
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_ga4_client.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement the GA4 client**

Create `services/ga4_client.py`:

```python
"""GA4 client.

Uses google-analytics-data's async client (BetaAnalyticsDataAsyncClient).
Runs two reports — engagement and conversion — and merges client-side on
pagePath. See spec Section 5 for why a single report cannot do this.
"""

from datetime import date
from typing import Any

from google.analytics.data_v1beta import BetaAnalyticsDataAsyncClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    DimensionFilter,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

from config import settings


SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _build_async_client() -> BetaAnalyticsDataAsyncClient:
    if not settings.google_application_credentials:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS must be set in .env")
    if not settings.ga4_property_id:
        raise RuntimeError("GA4_PROPERTY_ID must be set in .env")

    creds = service_account.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=SCOPES,
    )
    return BetaAnalyticsDataAsyncClient(credentials=creds)


def _blog_path_filter() -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name="pagePath",
            string_filter=Filter.StringFilter(
                value="/blog/",
                match_type=Filter.StringFilter.MatchType.CONTAINS,
            ),
        )
    )


async def query_blog_engagement(
    start_date: date, end_date: date
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Per-(pagePath, sourceMedium) engagement + per-pagePath CTA conversion.

    Returns a tuple:
      (engagement_rows, cta_clicks_by_path)

      engagement_rows: list of dicts with keys
        page_path, source_medium, active_users, engaged_sessions, avg_session_duration

      cta_clicks_by_path: dict mapping page_path → total signup_cta_click count

    Returning these separately (rather than denormalizing CTA into every
    engagement row) means downstream code doesn't have to dedupe a CTA
    count that's been duplicated across multiple source/medium splits.
    """
    client = _build_async_client()
    property_path = f"properties/{settings.ga4_property_id}"
    date_range = DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())

    # Report A: engagement, broken by source/medium.
    eng_request = RunReportRequest(
        property=property_path,
        date_ranges=[date_range],
        dimensions=[Dimension(name="pagePath"), Dimension(name="sessionSourceMedium")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="engagedSessions"),
            Metric(name="averageSessionDuration"),
        ],
        dimension_filter=_blog_path_filter(),
        limit=10000,
    )

    # Report B: conversion, filtered to the one event we care about.
    conv_request = RunReportRequest(
        property=property_path,
        date_ranges=[date_range],
        dimensions=[Dimension(name="pagePath"), Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            and_group=FilterExpressionList(expressions=[
                _blog_path_filter(),
                FilterExpression(filter=Filter(
                    field_name="eventName",
                    string_filter=Filter.StringFilter(
                        value="signup_cta_click",
                        match_type=Filter.StringFilter.MatchType.EXACT,
                    ),
                )),
            ])
        ),
        limit=10000,
    )

    eng_resp = await client.run_report(eng_request)
    conv_resp = await client.run_report(conv_request)

    # Aggregate conversion rows by pagePath.
    cta_by_path: dict[str, int] = {}
    for row in conv_resp.rows or []:
        page_path = row.dimension_values[0].value
        count = int(row.metric_values[0].value or 0)
        cta_by_path[page_path] = cta_by_path.get(page_path, 0) + count

    # Build engagement rows (no CTA field — that's returned separately).
    rows: list[dict[str, Any]] = []
    for row in eng_resp.rows or []:
        rows.append({
            "page_path": row.dimension_values[0].value,
            "source_medium": row.dimension_values[1].value,
            "active_users": int(row.metric_values[0].value or 0),
            "engaged_sessions": int(row.metric_values[1].value or 0),
            "avg_session_duration": float(row.metric_values[2].value or 0.0),
        })
    return rows, cta_by_path


async def validate() -> tuple[bool, str]:
    """Cheap check: one-row report today→today.

    Confirms the property ID + permission with a single Data API call.
    Avoids pulling in google-analytics-admin just for validation.
    """
    try:
        client = _build_async_client()
    except Exception as exc:  # noqa: BLE001
        return False, f"GA4 client build failed: {exc}"

    today = date.today().isoformat()
    request = RunReportRequest(
        property=f"properties/{settings.ga4_property_id}",
        date_ranges=[DateRange(start_date=today, end_date=today)],
        metrics=[Metric(name="activeUsers")],
        limit=1,
    )
    try:
        await client.run_report(request)
        return True, f"GA4 ok. Property: {settings.ga4_property_id}"
    except Exception as exc:  # noqa: BLE001
        return False, f"GA4 run_report failed: {exc}"
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_ga4_client.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/ga4_client.py tests/test_ga4_client.py tests/fixtures/ga4_engagement_response.json tests/fixtures/ga4_conversion_response.json
git commit -m "feat: add GA4 client with two-report merge

Engagement and conversion are two separate runReport calls merged
client-side on pagePath because a single dimension_filter on eventName
would scope all metrics to that event. Uses the async client; no
to_thread wrapping needed."
```

---

## Task 19: Extend `--mode validate` with GSC + GA4

**Files:**
- Modify: `agents/orchestrator.py`

- [ ] **Step 1: Update `run_validate`**

Open `agents/orchestrator.py`. Replace `run_validate`:

```python
async def run_validate() -> int:
    """Cheap end-to-end validation of external integrations.

    Checks DataForSEO, GSC, and GA4. Returns 0 on full success, 1 if any
    check failed. Each integration's failure is independent — a GSC fail
    does not prevent the GA4 check from running.
    """
    from services.dataforseo_client import get_client as get_dfs_client
    from services import gsc_client, ga4_client

    results: list[tuple[str, bool, str]] = []

    dfs = get_dfs_client()
    results.append(("DataForSEO", *(await dfs.validate())))

    results.append(("GSC", *(await gsc_client.validate())))

    results.append(("GA4", *(await ga4_client.validate())))

    all_ok = True
    for name, ok, message in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {message}")
        if not ok:
            all_ok = False

    return 0 if all_ok else 1
```

- [ ] **Step 2: Smoke-test**

If you've completed Section 5 of the spec's manual setup:
```bash
uv run python main.py --mode validate
```
Expected (with credentials set): three `[PASS]` lines. Without credentials, you'll see the corresponding `[FAIL]` line(s) with diagnostic detail.

- [ ] **Step 3: Commit**

```bash
git add agents/orchestrator.py
git commit -m "feat: extend --mode validate to cover GSC + GA4"
```

---

## Task 20: Implement `services/scoring.py`

**Files:**
- Create: `services/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring.py`:

```python
"""Pure threshold tests. No mocking needed."""


def test_score_position_thresholds():
    from services.scoring import score_position, Label
    assert score_position(1.0) == Label.good
    assert score_position(3.4) == Label.good
    assert score_position(4.0) == Label.borderline
    assert score_position(10.0) == Label.borderline
    assert score_position(11.0) == Label.poor
    assert score_position(99.9) == Label.poor


def test_score_ctr_relative_to_position():
    from services.scoring import score_ctr, Label
    # At position 3, expected CTR ~11%. 12% is GOOD.
    assert score_ctr(0.12, avg_position=3.0) == Label.good
    # 8% at position 3 is within 50% of expected (5.5%+) → BORDERLINE.
    assert score_ctr(0.08, avg_position=3.0) == Label.borderline
    # 2% at position 3 is <50% of expected → POOR.
    assert score_ctr(0.02, avg_position=3.0) == Label.poor


def test_score_impressions_insufficient_data_for_new_articles():
    from services.scoring import score_impressions, Label
    # Published 7 days ago — too early to judge.
    assert score_impressions(impressions=0, days_since_publish=7) == Label.insufficient_data
    assert score_impressions(impressions=50, days_since_publish=13) == Label.insufficient_data


def test_score_impressions_after_14_days():
    from services.scoring import score_impressions, Label
    assert score_impressions(impressions=200, days_since_publish=28) == Label.good
    assert score_impressions(impressions=50, days_since_publish=28) == Label.borderline
    assert score_impressions(impressions=5, days_since_publish=28) == Label.poor


def test_score_engagement_time():
    from services.scoring import score_engagement_time, Label
    assert score_engagement_time(seconds=150.0) == Label.good
    assert score_engagement_time(seconds=60.0) == Label.borderline
    assert score_engagement_time(seconds=15.0) == Label.poor


def test_score_cta_rate_insufficient_for_small_sample():
    from services.scoring import score_cta_rate, Label
    # <10 users → no verdict.
    assert score_cta_rate(clicks=0, users=5) == Label.insufficient_data


def test_score_cta_rate_with_enough_users():
    from services.scoring import score_cta_rate, Label
    # 5/100 = 5% → GOOD.
    assert score_cta_rate(clicks=5, users=100) == Label.good
    # 1/100 = 1% → BORDERLINE.
    assert score_cta_rate(clicks=1, users=100) == Label.borderline
    # 0/100 = 0% → POOR.
    assert score_cta_rate(clicks=0, users=100) == Label.poor
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `scoring.py`**

Create `services/scoring.py`:

```python
"""Pure scoring functions. The source of truth for thresholds.

The docs/playbooks/seo/04-measurement-cheatsheet.md table mirrors these for
the human reader. If a threshold changes here, update the playbook to match.
"""

from enum import StrEnum


class Label(StrEnum):
    good = "GOOD"
    borderline = "BORDERLINE"
    poor = "POOR"
    insufficient_data = "INSUFFICIENT_DATA"


# Position thresholds.
POSITION_GOOD_MAX = 3.5     # positions 1.0–3.49 → GOOD
POSITION_BORDERLINE_MAX = 10.5   # 3.5–10.49 → BORDERLINE; 10.5+ → POOR

# CTR thresholds are relative to position. The expected_ctr_for_position table
# is a rough industry baseline (Advanced Web Ranking / Backlinko studies).
_EXPECTED_CTR_BY_POSITION = [
    (1, 0.28), (2, 0.15), (3, 0.11), (4, 0.08), (5, 0.06),
    (6, 0.045), (7, 0.035), (8, 0.03), (9, 0.025), (10, 0.02),
    (15, 0.015), (20, 0.01), (50, 0.005),
]

# Impressions thresholds.
IMPRESSIONS_MIN_DAYS = 14
IMPRESSIONS_GOOD_MIN = 100
IMPRESSIONS_BORDERLINE_MIN = 10

# Engagement time (seconds).
ENGAGEMENT_GOOD_MIN = 120.0
ENGAGEMENT_BORDERLINE_MIN = 30.0

# CTA rate.
CTA_MIN_USERS = 10
CTA_GOOD_MIN = 0.02
CTA_BORDERLINE_MIN = 0.005


def score_position(avg_position: float) -> Label:
    if avg_position < POSITION_GOOD_MAX:
        return Label.good
    if avg_position < POSITION_BORDERLINE_MAX:
        return Label.borderline
    return Label.poor


def expected_ctr_for_position(pos: float) -> float:
    """Interpolate expected CTR between table anchors.

    Public so the measurement_agent can use the same baseline for the
    'reason' string it attaches to CTR scores — avoids a parallel
    source of truth.
    """
    table = _EXPECTED_CTR_BY_POSITION
    if pos <= table[0][0]:
        return table[0][1]
    if pos >= table[-1][0]:
        return table[-1][1]
    for (p_low, c_low), (p_high, c_high) in zip(table, table[1:]):
        if p_low <= pos <= p_high:
            t = (pos - p_low) / (p_high - p_low)
            return c_low + t * (c_high - c_low)
    return table[-1][1]


def score_ctr(ctr: float, avg_position: float) -> Label:
    expected = expected_ctr_for_position(avg_position)
    if ctr >= expected * 0.95:
        return Label.good
    if ctr >= expected * 0.5:
        return Label.borderline
    return Label.poor


def score_impressions(impressions: int, days_since_publish: int) -> Label:
    if days_since_publish < IMPRESSIONS_MIN_DAYS:
        return Label.insufficient_data
    if impressions >= IMPRESSIONS_GOOD_MIN:
        return Label.good
    if impressions >= IMPRESSIONS_BORDERLINE_MIN:
        return Label.borderline
    return Label.poor


def score_engagement_time(seconds: float) -> Label:
    if seconds >= ENGAGEMENT_GOOD_MIN:
        return Label.good
    if seconds >= ENGAGEMENT_BORDERLINE_MIN:
        return Label.borderline
    return Label.poor


def score_cta_rate(clicks: int, users: int) -> Label:
    if users < CTA_MIN_USERS:
        return Label.insufficient_data
    rate = clicks / users
    if rate >= CTA_GOOD_MIN:
        return Label.good
    if rate >= CTA_BORDERLINE_MIN:
        return Label.borderline
    return Label.poor
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add services/scoring.py tests/test_scoring.py
git commit -m "feat: add scoring thresholds with INSUFFICIENT_DATA support

Pure functions, source of truth for the playbook's threshold table.
Position-aware CTR scoring. <14 days post-publish returns
INSUFFICIENT_DATA rather than misleading POOR."
```

---

## Task 21: Implement `models/measurement.py` with dataclasses + helpers

**Files:**
- Create: `models/measurement.py`
- Create: `tests/test_measurement.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_measurement.py`:

```python
"""Tests for the deterministic measurement dataclasses + url normalization
+ report_to_synthesis_input helper."""


def test_normalize_url_strips_query_and_fragment():
    from models.measurement import normalize_url
    assert normalize_url("https://www.draftandarc.com/blog/foo/?utm=x#a") == \
        "https://www.draftandarc.com/blog/foo"


def test_normalize_url_strips_trailing_slash():
    from models.measurement import normalize_url
    assert normalize_url("https://www.draftandarc.com/blog/foo/") == \
        "https://www.draftandarc.com/blog/foo"


def test_normalize_url_lowercases_host():
    from models.measurement import normalize_url
    assert normalize_url("https://WWW.DraftAndArc.com/blog/Foo") == \
        "https://www.draftandarc.com/blog/Foo"


def test_normalize_url_returns_empty_on_empty():
    from models.measurement import normalize_url
    assert normalize_url("") == ""
    assert normalize_url(None) == ""


def test_report_to_synthesis_input_includes_per_article_data():
    from models.measurement import (
        MeasurementReport, ScoredArticlePerformance, MetricScore,
        GapOpportunity, DataSourceStatus, report_to_synthesis_input,
    )
    from services.scoring import Label

    report = MeasurementReport(
        window_start="2026-04-21",
        window_end="2026-05-16",
        headline={"articles": 1, "impressions": 800, "clicks": 32},
        per_article=[
            ScoredArticlePerformance(
                article_id="tutorial-hell-progress",
                url="https://www.draftandarc.com/blog/tutorial-hell-progress",
                published_at="2026-04-27",
                days_since_publish=22,
                overall_label=Label.borderline,
                metrics={
                    "position": MetricScore(value=12.3, display="pos 12.3", label=Label.poor, reason="page 2"),
                    "ctr": MetricScore(value=0.04, display="4.0%", label=Label.poor, reason="below expected"),
                },
                top_queries=[],
            )
        ],
        gap_opportunities=[
            GapOpportunity(keyword="tutorial hell python", position=28.0, volume=90, url="..."),
        ],
        data_source_status=DataSourceStatus(gsc_ok=True, ga4_ok=True, dfs_ok=True, notes=[]),
    )

    text = report_to_synthesis_input(report)
    assert "tutorial-hell-progress" in text
    assert "12.3" in text
    assert "tutorial hell python" in text
    assert "Window: 2026-04-21 to 2026-05-16" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_measurement.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the module**

Create `models/measurement.py`:

```python
"""Deterministic measurement dataclasses + URL normalization + LLM-input helper.

Schema split (see spec Section 6): anything with a number lives here as a
plain dataclass and is never produced by an LLM. The LLM-produced fields
(actions, verdicts, coverage_note) live in output_schemas.py as Pydantic
models.
"""

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlunparse

from services.scoring import Label


@dataclass
class MetricScore:
    value: float
    display: str          # formatted for render: "4.0%", "pos 12.3", "1:42"
    label: Label
    reason: str           # one-line plain English


@dataclass
class QueryRow:
    query: str
    impressions: int
    clicks: int
    ctr: float
    position: float


@dataclass
class ScoredArticlePerformance:
    article_id: str
    url: str
    published_at: str             # ISO date
    days_since_publish: int
    overall_label: Label
    metrics: dict[str, MetricScore] = field(default_factory=dict)
    top_queries: list[QueryRow] = field(default_factory=list)


@dataclass
class GapOpportunity:
    keyword: str
    position: float
    volume: int
    url: str                      # which of our URLs ranks for it


@dataclass
class DataSourceStatus:
    gsc_ok: bool
    ga4_ok: bool
    dfs_ok: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class MeasurementReport:
    window_start: str             # ISO date
    window_end: str               # effective end after GSC's 3-day lag
    headline: dict[str, float | int] = field(default_factory=dict)
    per_article: list[ScoredArticlePerformance] = field(default_factory=list)
    gap_opportunities: list[GapOpportunity] = field(default_factory=list)
    data_source_status: DataSourceStatus = field(
        default_factory=lambda: DataSourceStatus(False, False, False, [])
    )


@dataclass
class FinalMeasurementReport:
    """Deterministic report + LLM-produced prose, merged. Both renderers consume this type."""
    report: MeasurementReport
    actions: list                 # list[MeasurementActionOutput], typed Any to avoid Pydantic circular import
    verdicts: dict[str, str]      # article_id → verdict prose
    coverage_note: str            # LLM coverage prose, with any deterministic status notes prepended


def normalize_url(url: Optional[str]) -> str:
    """Normalize for exact-match URL joins.

    - Lowercase host
    - Strip trailing slash from path
    - Strip query string and fragment
    """
    if not url:
        return ""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").rstrip("/")
    return urlunparse((parsed.scheme, host, path, "", "", ""))


def report_to_synthesis_input(report: MeasurementReport) -> str:
    """Render the deterministic report into a compact text summary for the LLM.

    Kept as a pure function so it's trivially unit-testable: input report →
    expected prompt fragment. The agent passes the result of this into the
    measurement_synthesis chain as `raw_data`.
    """
    lines = [
        f"## Measurement Report",
        f"Window: {report.window_start} to {report.window_end}",
        "",
        "### Headline",
    ]
    for k, v in report.headline.items():
        lines.append(f"  - {k}: {v}")

    lines.extend(["", "### Per-article performance"])
    for a in report.per_article:
        lines.append(f"")
        lines.append(f"#### {a.article_id} (published {a.published_at}, {a.days_since_publish} days ago)")
        lines.append(f"URL: {a.url}")
        lines.append(f"Overall: {a.overall_label.value}")
        for metric_name, score in a.metrics.items():
            lines.append(f"  - {metric_name}: {score.display}  [{score.label.value}] — {score.reason}")
        if a.top_queries:
            lines.append("Top surfacing queries:")
            for q in a.top_queries[:5]:
                lines.append(f"  - {q.query!r}: {q.impressions} impr / {q.clicks} clicks / pos {q.position:.1f}")

    if report.gap_opportunities:
        lines.extend(["", "### Domain-level gap opportunities"])
        for g in report.gap_opportunities[:10]:
            lines.append(f"  - {g.keyword!r}: pos {g.position:.0f}, volume {g.volume} (URL: {g.url})")

    status = report.data_source_status
    if not (status.gsc_ok and status.ga4_ok and status.dfs_ok) or status.notes:
        lines.extend(["", "### Data source status"])
        lines.append(f"  GSC: {'ok' if status.gsc_ok else 'FAILED'}")
        lines.append(f"  GA4: {'ok' if status.ga4_ok else 'FAILED'}")
        lines.append(f"  DataForSEO: {'ok' if status.dfs_ok else 'FAILED'}")
        for note in status.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_measurement.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add models/measurement.py tests/test_measurement.py
git commit -m "feat: add measurement dataclasses + URL normalization + LLM input helper

Deterministic side of the schema split (spec Section 6). Numbers
live here as dataclasses, never produced by an LLM.
report_to_synthesis_input renders the report compactly for the
LLM's synthesis step."
```

---

## Task 22: Add `published_at` and `live_url` to `ContentCalendarEntry`

**Files:**
- Modify: `models/article.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Add the fields**

Open `models/article.py`. Update `ContentCalendarEntry`:

```python
from enum import StrEnum
from typing import Optional
from pydantic import BaseModel


class ArticleStatus(StrEnum):
    planned = "planned"
    in_progress = "in_progress"
    ready_for_review = "ready_for_review"
    needs_review_flagged = "needs_review_flagged"
    shelved = "shelved"
    published = "published"


class ArticleType(StrEnum):
    standard = "standard"
    topic_teaser = "topic_teaser"


class ContentCalendarEntry(BaseModel):
    id: str
    status: ArticleStatus = ArticleStatus.planned
    title: str
    primary_keyword: str
    secondary_keywords: list[str] = []
    search_intent: str = "informational"
    article_type: ArticleType
    target_audience: str
    angle: str
    meta_description: str
    suggested_headings: list[str] = []
    cta_prompt: str = ""
    blog_category: str = "Study Methods"
    draft_path: Optional[str] = None
    pr_url: Optional[str] = None
    published_at: Optional[str] = None   # NEW. ISO date. Set by --mark-published.
    live_url: Optional[str] = None        # NEW. Canonical URL. Set by --mark-published.
```

- [ ] **Step 2: Confirm backwards compatibility**

Run: `uv run python -c "from models.article import ContentCalendarEntry, ArticleType; e = ContentCalendarEntry(id='x', title='t', primary_keyword='k', article_type=ArticleType.standard, target_audience='a', angle='b', meta_description='m'); print(e.published_at, e.live_url)"`
Expected: `None None`.

Verify the existing `content_calendar.json` can still be loaded:
```bash
uv run python -c "import asyncio; from services.calendar_service import load_calendar; print(asyncio.run(load_calendar())[0].id)"
```
Expected: prints an article id (no JSON parse errors).

- [ ] **Step 3: Commit**

```bash
git add models/article.py
git commit -m "feat: add published_at and live_url to ContentCalendarEntry

Both Optional with None defaults — existing calendar entries load
unchanged. Set by --mark-published <id> --url <live_url> (Task 25)."
```

---

## Task 23: Implement `renderers/measurement_md.py`

**Files:**
- Modify: `renderers/__init__.py` (created as empty in Task 5)
- Create: `renderers/measurement_md.py`
- Create: `tests/test_renderers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_renderers.py`:

```python
"""Renderer tests. Snapshot-style: feed a known report, check key strings appear."""

from dataclasses import dataclass


def _sample_final_report():
    from models.measurement import (
        MeasurementReport, ScoredArticlePerformance, MetricScore,
        GapOpportunity, DataSourceStatus,
    )
    from services.scoring import Label

    report = MeasurementReport(
        window_start="2026-04-21",
        window_end="2026-05-16",
        headline={"articles": 1, "impressions": 800, "clicks": 32, "ctr": 0.04, "avg_position": 12.3},
        per_article=[
            ScoredArticlePerformance(
                article_id="tutorial-hell-progress",
                url="https://www.draftandarc.com/blog/tutorial-hell-progress",
                published_at="2026-04-27",
                days_since_publish=22,
                overall_label=Label.borderline,
                metrics={
                    "position": MetricScore(value=12.3, display="pos 12.3", label=Label.poor, reason="page 2"),
                    "ctr": MetricScore(value=0.04, display="4.0%", label=Label.poor, reason="below expected"),
                },
                top_queries=[],
            )
        ],
        gap_opportunities=[
            GapOpportunity(keyword="tutorial hell python", position=28.0, volume=90, url="..."),
        ],
        data_source_status=DataSourceStatus(gsc_ok=True, ga4_ok=True, dfs_ok=True),
    )

    @dataclass
    class _Final:
        report: object
        actions: list
        verdicts: dict
        coverage_note: str

    return _Final(
        report=report,
        actions=[],
        verdicts={"tutorial-hell-progress": "Ranking on page 2 with CTR below expected — title rewrite candidate."},
        coverage_note="GSC, GA4, and DataForSEO all reporting normally.",
    )


def test_measurement_md_includes_terse_per_article_data():
    from renderers.measurement_md import render_md
    md = render_md(_sample_final_report())

    # Header
    assert "Measurement Brief" in md
    assert "2026-04-21" in md
    # Per-article block
    assert "tutorial-hell-progress" in md
    assert "pos 12.3" in md  # raw display, agent reads numbers
    # Verdict
    assert "title rewrite candidate" in md
    # Gap opportunity
    assert "tutorial hell python" in md
    # Coverage
    assert "GSC, GA4, and DataForSEO" in md


def test_measurement_md_omits_glossary_and_score_badges():
    """The agent-facing MD must NOT contain the human-only education."""
    from renderers.measurement_md import render_md
    md = render_md(_sample_final_report())

    assert "Glossary" not in md
    assert "[GOOD]" not in md
    assert "[POOR]" not in md   # raw numbers only, no badges
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_renderers.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the MD renderer**

Create `renderers/measurement_md.py`:

```python
"""Markdown renderer for the SEO agent.

Terse, no glossary, no score badges. The agent reads numbers; humans get
the HTML renderer (Task 24).
"""


def render_md(final) -> str:
    """Render the final report as markdown for the SEO agent."""
    report = final.report
    lines = [
        f"## Measurement Brief — {report.window_end}",
        f"Window: {report.window_start} to {report.window_end}",
        "",
        "### Headline",
    ]
    h = report.headline
    if "articles" in h:
        lines.append(f"- Articles published: {h.get('articles', 0)}")
    if "impressions" in h:
        ctr_pct = h.get("ctr", 0.0) * 100
        lines.append(
            f"- Impressions: {h.get('impressions', 0):,} | "
            f"Clicks: {h.get('clicks', 0):,} | "
            f"CTR: {ctr_pct:.1f}% | "
            f"Avg position: {h.get('avg_position', 0):.1f}"
        )

    if report.per_article:
        lines.extend(["", "### Per-article performance"])
        for a in report.per_article:
            lines.append("")
            lines.append(f"#### {a.article_id} (published {a.published_at})")
            lines.append(f"URL: {a.url}")
            for metric_name, score in a.metrics.items():
                lines.append(f"- {metric_name}: {score.display}")
            if a.top_queries:
                lines.append("- Top surfacing queries:")
                for q in a.top_queries[:5]:
                    pct = q.ctr * 100
                    lines.append(
                        f"  - \"{q.query}\" — {q.impressions} impr / {q.clicks} clicks / "
                        f"{pct:.1f}% CTR / pos {q.position:.1f}"
                    )
            verdict = final.verdicts.get(a.article_id, "")
            if verdict:
                lines.append(f"- Verdict: {verdict}")

    if report.gap_opportunities:
        lines.extend(["", "### Domain-level gap opportunities"])
        lines.append("Keywords we rank for but did not target:")
        for g in report.gap_opportunities[:10]:
            lines.append(f"- \"{g.keyword}\" — pos {g.position:.0f}, volume {g.volume}")

    if final.actions:
        lines.extend(["", "### Recommended actions"])
        for action in final.actions:
            lines.append(f"{action.priority.upper()}: {action.action}")
            if action.affected_article_id != "n/a":
                lines.append(f"   (affects: {action.affected_article_id})")
            lines.append(f"   Rationale: {action.rationale}")

    if final.coverage_note:
        lines.extend(["", "### Coverage note", final.coverage_note])

    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_renderers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add renderers/__init__.py renderers/measurement_md.py tests/test_renderers.py
git commit -m "feat: add MD renderer for measurement brief (agent-facing, terse)"
```

---

## Task 24: Implement `renderers/measurement_html.py` + Jinja2 template

**Files:**
- Create: `renderers/measurement_html.py`
- Create: `renderers/templates/__init__.py`
- Create: `renderers/templates/measurement.html.j2`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Create the Jinja2 template**

Create `renderers/templates/measurement.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Measurement Brief — {{ window_end }}</title>
<style>
  body { font: 14px/1.5 -apple-system, system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #0f172a; }
  h1, h2, h3 { line-height: 1.2; }
  h1 { font-size: 1.7rem; margin: 0 0 0.4rem; }
  h2 { font-size: 1.25rem; margin-top: 2rem; }
  h3 { font-size: 1rem; margin-top: 1.2rem; }
  .meta { color: #64748b; margin-bottom: 1.5rem; }
  .glossary { background: #f1f5f9; padding: 1rem 1.25rem; border-radius: 6px; margin: 1rem 0 2rem; }
  .glossary dt { font-weight: 600; margin-top: 0.5rem; }
  .glossary dd { margin: 0.1rem 0 0.5rem; color: #334155; }
  .article-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem 1.25rem; margin: 1rem 0; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em; vertical-align: middle; }
  .badge-good        { background: #16a34a; color: #fff; }
  .badge-borderline  { background: #f59e0b; color: #0f172a; }
  .badge-poor        { background: #dc2626; color: #fff; }
  .badge-insufficient_data { background: #94a3b8; color: #fff; }
  .metric-row { display: flex; gap: 0.5rem; margin: 0.35rem 0; align-items: baseline; }
  .metric-name { width: 12rem; color: #475569; font-weight: 500; }
  .metric-value { font-variant-numeric: tabular-nums; min-width: 5rem; }
  .metric-reason { color: #64748b; font-size: 0.9rem; }
  .verdict { margin: 0.8rem 0 0.2rem; font-style: italic; color: #1e293b; }
  .action { padding: 0.5rem 0.8rem; border-left: 4px solid #94a3b8; margin: 0.5rem 0; background: #f8fafc; }
  .action.high   { border-left-color: #dc2626; }
  .action.medium { border-left-color: #f59e0b; }
  .action.low    { border-left-color: #16a34a; }
  details { margin: 0.3rem 0 0.6rem; }
  summary { cursor: pointer; color: #64748b; font-size: 0.9rem; }
</style>
</head>
<body>

<h1>Measurement Brief</h1>
<div class="meta">Window: {{ window_start }} to {{ window_end }}{% if effective_end_note %} — {{ effective_end_note }}{% endif %}</div>

<section class="glossary">
  <h2>Glossary</h2>
  <dl>
    <dt>Impressions</dt>
    <dd>How many times your URL appeared in Google search results.</dd>
    <dt>Clicks</dt>
    <dd>How many impressions turned into actual visits. Combined with impressions → CTR.</dd>
    <dt>CTR (Click-Through Rate)</dt>
    <dd>Clicks ÷ impressions. The "is the title compelling?" metric. Low CTR at a good position = rewrite the title.</dd>
    <dt>Average position</dt>
    <dd>Where your URL ranked, averaged across impressions. Lower is better. 1–3 = real traffic; 11+ = essentially zero clicks.</dd>
    <dt>Engaged sessions (GA4)</dt>
    <dd>Sessions that lasted 10+ seconds, had a conversion event, or had 2+ pageviews. The "did they actually read it?" metric.</dd>
    <dt>CTA click rate</dt>
    <dd>Clicks on the "Try Draft and Arc" link ÷ visitors. Industry baseline is 1–3%.</dd>
  </dl>
</section>

<section>
  <h2>Headline</h2>
  <ul>
    <li>Articles published: {{ headline.get("articles", 0) }}</li>
    {% if "impressions" in headline %}
    <li>Impressions: {{ "{:,}".format(headline["impressions"]) }} | Clicks: {{ "{:,}".format(headline.get("clicks", 0)) }} | CTR: {{ "{:.1f}".format(headline.get("ctr", 0) * 100) }}% | Avg position: {{ "{:.1f}".format(headline.get("avg_position", 0)) }}</li>
    {% endif %}
  </ul>
</section>

{% if per_article %}
<section>
  <h2>Per-article performance</h2>
  {% for a in per_article %}
  <div class="article-card">
    <h3>{{ a.article_id }} <span class="badge badge-{{ a.overall_label.value | lower }}">{{ a.overall_label.value }}</span></h3>
    <div class="meta">Published {{ a.published_at }} · {{ a.days_since_publish }} days ago · <a href="{{ a.url }}">{{ a.url }}</a></div>
    {% for metric_name, score in a.metrics.items() %}
    <div class="metric-row">
      <span class="metric-name">{{ metric_name }}</span>
      <span class="metric-value">{{ score.display }}</span>
      <span class="badge badge-{{ score.label.value | lower }}">{{ score.label.value }}</span>
      <span class="metric-reason">— {{ score.reason }}</span>
    </div>
    {% endfor %}

    {% if a.top_queries %}
    <details><summary>Top surfacing queries ({{ a.top_queries | length }})</summary>
      <ul>
      {% for q in a.top_queries[:5] %}
        <li>"{{ q.query }}" — {{ q.impressions }} impr / {{ q.clicks }} clicks / {{ "{:.1f}".format(q.ctr * 100) }}% CTR / pos {{ "{:.1f}".format(q.position) }}</li>
      {% endfor %}
      </ul>
    </details>
    {% endif %}

    {% if verdicts.get(a.article_id) %}
    <div class="verdict">{{ verdicts[a.article_id] }}</div>
    {% endif %}
  </div>
  {% endfor %}
</section>
{% endif %}

{% if gap_opportunities %}
<section>
  <h2>Domain-level gap opportunities</h2>
  <p class="meta">Keywords your domain ranks for but you didn't target. These are usually easy follow-ups.</p>
  <ul>
  {% for g in gap_opportunities[:10] %}
    <li>"{{ g.keyword }}" — pos {{ "{:.0f}".format(g.position) }}, volume {{ g.volume }} (ranks at: <a href="{{ g.url }}">{{ g.url }}</a>)</li>
  {% endfor %}
  </ul>
</section>
{% endif %}

{% if actions %}
<section>
  <h2>Recommended actions</h2>
  {% for action in actions %}
  <div class="action {{ action.priority }}">
    <strong>{{ action.priority.upper() }}:</strong> {{ action.action }}
    {% if action.affected_article_id != "n/a" %}
    <div class="meta">Affects: {{ action.affected_article_id }}</div>
    {% endif %}
    <div class="metric-reason">{{ action.rationale }}</div>
  </div>
  {% endfor %}
</section>
{% endif %}

{% if coverage_note %}
<section>
  <h2>Coverage note</h2>
  <p>{{ coverage_note }}</p>
</section>
{% endif %}

</body>
</html>
```

- [ ] **Step 2: Implement the HTML renderer**

Create `renderers/templates/__init__.py` (empty file).

Create `renderers/measurement_html.py`:

```python
"""HTML renderer for the human dashboard.

Self-contained: CSS inlined, no JS, no external resources. Emailable,
archivable, works offline.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "htm"]),
    trim_blocks=False,
    lstrip_blocks=False,
)


def render_html(final, *, effective_end_note: str = "") -> str:
    """Render the final report as a self-contained HTML page for the operator."""
    template = _env.get_template("measurement.html.j2")
    report = final.report
    return template.render(
        window_start=report.window_start,
        window_end=report.window_end,
        effective_end_note=effective_end_note,
        headline=report.headline,
        per_article=report.per_article,
        gap_opportunities=report.gap_opportunities,
        actions=final.actions,
        verdicts=final.verdicts,
        coverage_note=final.coverage_note,
    )
```

- [ ] **Step 3: Add an HTML test**

Append to `tests/test_renderers.py`:

```python
def test_measurement_html_renders_glossary_and_badges():
    from renderers.measurement_html import render_html
    html = render_html(_sample_final_report())

    # Glossary is present (HTML only).
    assert "Glossary" in html
    assert "Click-Through Rate" in html
    # Badges with colors.
    assert "badge-borderline" in html
    assert "badge-poor" in html
    # Same data is present.
    assert "tutorial-hell-progress" in html
    assert "tutorial hell python" in html
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_renderers.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add renderers/measurement_html.py renderers/templates/__init__.py renderers/templates/measurement.html.j2 tests/test_renderers.py
git commit -m "feat: add HTML renderer + Jinja2 template

Self-contained dashboard with glossary, colored badges, and
foldable per-article cards. Same data as MD; different audience."
```

---

## Task 25: Add `mark_published` to calendar_service + `--mark-published` CLI

**Files:**
- Modify: `services/calendar_service.py`
- Modify: `main.py`
- Create: `tests/test_calendar_mark_published.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_calendar_mark_published.py`:

```python
"""--mark-published sets status, published_at, and live_url atomically."""

from pathlib import Path
from unittest.mock import patch

import pytest


async def test_mark_published_sets_three_fields(tmp_path: Path):
    """Round-trip: load, mark, save, reload — fields persist."""
    from services import calendar_service
    from models.article import ContentCalendarEntry, ArticleType, ArticleStatus
    import json

    calendar_path = tmp_path / "content_calendar.json"

    entries = [
        ContentCalendarEntry(
            id="tutorial-hell-progress",
            status=ArticleStatus.ready_for_review,
            title="...",
            primary_keyword="...",
            article_type=ArticleType.standard,
            target_audience="...",
            angle="...",
            meta_description="...",
        )
    ]
    calendar_path.write_text(json.dumps([e.model_dump() for e in entries], indent=2))

    with patch.object(calendar_service, "CALENDAR_PATH", calendar_path):
        await calendar_service.mark_published(
            "tutorial-hell-progress",
            live_url="https://www.draftandarc.com/blog/tutorial-hell-progress",
            published_on="2026-05-20",
        )
        reloaded = await calendar_service.load_calendar()

    target = next(e for e in reloaded if e.id == "tutorial-hell-progress")
    assert target.status == ArticleStatus.published
    assert target.published_at == "2026-05-20"
    assert target.live_url == "https://www.draftandarc.com/blog/tutorial-hell-progress"


async def test_mark_published_raises_on_missing_id(tmp_path: Path):
    from services import calendar_service
    import json

    calendar_path = tmp_path / "content_calendar.json"
    calendar_path.write_text("[]")

    with patch.object(calendar_service, "CALENDAR_PATH", calendar_path):
        with pytest.raises(ValueError, match="not found"):
            await calendar_service.mark_published(
                "nonexistent",
                live_url="https://www.draftandarc.com/blog/x",
            )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_calendar_mark_published.py -v`
Expected: FAIL with `AttributeError: module 'services.calendar_service' has no attribute 'mark_published'`.

- [ ] **Step 3: Implement `mark_published`**

Append to `services/calendar_service.py`:

```python
from datetime import date as _date_module


async def mark_published(
    entry_id: str,
    *,
    live_url: str,
    published_on: Optional[str] = None,
) -> None:
    """Set status=published, published_at, and live_url on one calendar entry.

    `published_on` defaults to today's ISO date.
    Raises ValueError if `entry_id` is not in the calendar.
    """
    entries = await load_calendar()
    target = next((e for e in entries if e.id == entry_id), None)
    if target is None:
        raise ValueError(f"Calendar entry {entry_id!r} not found")

    target.status = ArticleStatus.published
    target.published_at = published_on or _date_module.today().isoformat()
    target.live_url = live_url

    await save_calendar(entries)
```

- [ ] **Step 4: Wire `--mark-published` into `main.py`**

Open `main.py`. Add to the argparse setup:

```python
    parser.add_argument(
        "--mark-published",
        metavar="ARTICLE_ID",
        help="Mark a calendar entry as published. Requires --url.",
    )
    parser.add_argument(
        "--url",
        metavar="LIVE_URL",
        help="Canonical URL of the published article (used with --mark-published).",
    )
```

Make `--mode` optional when `--mark-published` is used. In `_build_parser`, change:
```python
parser.add_argument(
    "--mode",
    choices=["setup", "weekly", "article", "validate"],
    required=False,
    help="setup | weekly | article | validate",
)
```

Add a new handler:

```python
async def _run_mark_published(article_id: str, url: str) -> None:
    from services.calendar_service import mark_published
    if not url:
        raise SystemExit("--mark-published requires --url <canonical-url>")
    await mark_published(article_id, live_url=url)
    print(f"Marked {article_id!r} as published with URL {url}")
```

Update `main()`:

```python
def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mark_published:
        asyncio.run(_run_mark_published(args.mark_published, args.url or ""))
        return

    if not args.mode:
        parser.error("--mode is required unless --mark-published is given")

    if args.mode == "setup":
        asyncio.run(_run_setup())
    elif args.mode == "weekly":
        asyncio.run(_run_weekly())
    elif args.mode == "article":
        asyncio.run(_run_article())
    elif args.mode == "validate":
        asyncio.run(_run_validate())
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_calendar_mark_published.py -v`
Expected: PASS.

- [ ] **Step 6: Smoke-test the CLI**

Run: `uv run python main.py --mark-published nonexistent --url https://x/`
Expected: prints `ValueError: Calendar entry 'nonexistent' not found` (or similar).

- [ ] **Step 7: Commit**

```bash
git add services/calendar_service.py main.py tests/test_calendar_mark_published.py
git commit -m "feat: add --mark-published CLI + mark_published service

Sets status, published_at, and live_url atomically via atomic_write_text.
Required to make articles measurable; spec Section 6 'calendar hygiene'."
```

---

## Task 26: Add measurement LLM schemas to `output_schemas.py`

**Files:**
- Modify: `output_schemas.py`

- [ ] **Step 1: Add the schemas**

Open `output_schemas.py`. Append:

```python
class MeasurementActionOutput(_StrictModel):
    priority: str                 # high | medium | low
    action: str                   # 1–2 sentence imperative
    affected_article_id: str      # calendar entry id, or "n/a" for net-new
    rationale: str                # why this action, citing data


class ArticleVerdictOutput(_StrictModel):
    article_id: str               # must match a ScoredArticlePerformance id
    verdict: str                  # one-line prose verdict


class MeasurementBriefOutput(_StrictModel):
    actions: list[MeasurementActionOutput]
    article_verdicts: list[ArticleVerdictOutput]
    coverage_note: str
```

- [ ] **Step 2: Confirm parses**

Run: `uv run python -c "from output_schemas import MeasurementBriefOutput; print(MeasurementBriefOutput(actions=[], article_verdicts=[], coverage_note='').coverage_note)"`
Expected: prints `` (empty string).

- [ ] **Step 3: Commit**

```bash
git add output_schemas.py
git commit -m "feat: add measurement LLM output schemas

MeasurementBriefOutput is what the synthesis chain produces.
Numbers stay on the deterministic side (models/measurement.py)."
```

---

## Task 27: Create the measurement synthesis prompt

**Files:**
- Create: `prompts/md/chains/measurement_synthesis.md`

- [ ] **Step 1: Write the prompt**

Create `prompts/md/chains/measurement_synthesis.md`:

```markdown
You are the Measurement Synthesis chain. You read a deterministic SEO measurement report and produce three things only: action recommendations, per-article prose verdicts, and a coverage note.

# CRITICAL RULES

- You do NOT emit numbers. Every number in your input was computed deterministically and is the truth. Refer to numbers in prose by quoting them ("at position 12.3", "CTR of 4%"), never by recomputing or rounding them.
- You do NOT invent articles. Every `affected_article_id` you produce MUST match an `article_id` from the input report. If you want to recommend a net-new article, use `"n/a"` as the `affected_article_id`.
- Per-article verdicts MUST have `article_id` matching the input.

# HOW TO PRIORITIZE ACTIONS

Three priority levels:

- **HIGH**: an article is published 14+ days, has zero or near-zero impressions, AND the indexing-check action would resolve the unknown. Or: an article has GOOD position but POOR CTR — title rewrite is high-leverage.
- **MEDIUM**: gap opportunities (we rank for a keyword we didn't target) where a focused follow-up article would likely move into top 10.
- **LOW**: minor improvements, content refreshes on articles already performing acceptably, or experiments.

Never produce more than 5 actions. The point is decision-readiness, not exhaustive coverage.

# COVERAGE NOTE

One short paragraph. Mentions:
- Any failed data sources (from `data_source_status` if present).
- Any caveats (early data, missing CTA event wiring, etc.).
- If everything is normal: "All three data sources reporting normally; X articles in measurement window."

# VERDICTS

One sentence per published article. Plain English. Connects the metrics to what to do about them, but the imperative belongs in `actions`, not in the verdict. Examples:

- "Borderline ranking with CTR below expected — title rewrite is the high-leverage fix."
- "Strong page-1 position and engagement; the angle is working."
- "Published 8 days ago — too early to judge; check again next cycle."

---HUMAN---
DETERMINISTIC MEASUREMENT REPORT (numbers are authoritative — do not recompute):

{raw_data}

PRODUCT FACTS (for context only — do not invent product features):

{product_facts}

Produce one MeasurementBriefOutput now: at most 5 actions, one verdict per published article, one coverage_note paragraph.
```

- [ ] **Step 2: Confirm it loads**

Run: `uv run python -c "from prompts.loader import load_prompt; load_prompt('chains/measurement_synthesis.md'); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add prompts/md/chains/measurement_synthesis.md
git commit -m "feat: add measurement synthesis prompt

Explicitly forbids the LLM from emitting numbers (those come from
the deterministic report) and from inventing article IDs."
```

---

## Task 28: Implement `agents/measurement_agent.py`

**Files:**
- Create: `agents/measurement_agent.py`
- Create: `tests/test_measurement_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_measurement_agent.py`:

```python
"""End-to-end measurement agent. All external clients mocked at the boundary."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_run_measure_assembles_full_report():
    """Full pipeline: GSC + GA4 + DFS Labs → report → render. LLM synthesis mocked."""
    from agents import measurement_agent
    from models.article import ContentCalendarEntry, ArticleStatus, ArticleType
    from output_schemas import MeasurementBriefOutput, ArticleVerdictOutput

    # Calendar has one published article with live_url.
    entries = [
        ContentCalendarEntry(
            id="tutorial-hell-progress",
            status=ArticleStatus.published,
            title="...",
            primary_keyword="tutorial hell",
            secondary_keywords=["stop watching tutorials"],
            article_type=ArticleType.standard,
            target_audience="...",
            angle="...",
            meta_description="...",
            published_at="2026-04-27",
            live_url="https://www.draftandarc.com/blog/tutorial-hell-progress",
        )
    ]

    gsc_rows = [
        {
            "page": "https://www.draftandarc.com/blog/tutorial-hell-progress",
            "query": "how to get rid of tutorial hell",
            "clicks": 8, "impressions": 142, "ctr": 0.0563, "position": 9.2,
        },
    ]

    ga4_rows = [
        {
            "page_path": "/blog/tutorial-hell-progress",
            "source_medium": "google / organic",
            "active_users": 24, "engaged_sessions": 18,
            "avg_session_duration": 102.5,
        }
    ]
    ga4_cta_by_path = {"/blog/tutorial-hell-progress": 2}

    dfs_ranked = [
        {"keyword": "tutorial hell python", "position": 28.0, "volume": 90,
         "url": "https://www.draftandarc.com/blog/tutorial-hell-progress"},
    ]

    mock_synthesis_output = MeasurementBriefOutput(
        actions=[],
        article_verdicts=[
            ArticleVerdictOutput(
                article_id="tutorial-hell-progress",
                verdict="On page 1 — keep the angle.",
            )
        ],
        coverage_note="All three sources reporting normally.",
    )

    with patch("agents.measurement_agent.load_calendar", AsyncMock(return_value=entries)), \
         patch("agents.measurement_agent.gsc_client") as mock_gsc, \
         patch("agents.measurement_agent.ga4_client") as mock_ga4, \
         patch("agents.measurement_agent.get_dfs_client") as mock_get_dfs, \
         patch("agents.measurement_agent.get_llm") as mock_get_llm, \
         patch("agents.measurement_agent.file_service.read_text", AsyncMock(return_value="## Product Facts\n- x")):

        mock_gsc.query_blog_performance = AsyncMock(return_value=gsc_rows)
        mock_ga4.query_blog_engagement = AsyncMock(return_value=(ga4_rows, ga4_cta_by_path))

        mock_dfs = MagicMock()
        mock_dfs.ranked_keywords_for_site = AsyncMock(return_value=dfs_ranked)
        mock_get_dfs.return_value = mock_dfs

        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_synthesis_output)
        mock_llm.with_structured_output.return_value = mock_chain
        mock_get_llm.return_value = mock_llm

        final_report = await measurement_agent.run_measurement_agent(days=28)

    # Deterministic side intact.
    assert len(final_report.report.per_article) == 1
    article = final_report.report.per_article[0]
    assert article.article_id == "tutorial-hell-progress"
    assert "position" in article.metrics
    # LLM-side merged in.
    assert "page 1" in final_report.verdicts["tutorial-hell-progress"].lower()
    # Deterministic status notes prepended to LLM coverage_note.
    assert "All three sources" in final_report.coverage_note


async def test_run_measure_surfaces_skipped_articles_missing_live_url():
    """A published entry missing live_url MUST appear in coverage_note,
    not silently disappear from the brief (spec backfill note)."""
    from agents import measurement_agent
    from models.article import ContentCalendarEntry, ArticleStatus, ArticleType
    from output_schemas import MeasurementBriefOutput

    entries = [
        ContentCalendarEntry(
            id="legacy-article",
            status=ArticleStatus.published,
            title="...",
            primary_keyword="...",
            secondary_keywords=[],
            article_type=ArticleType.standard,
            target_audience="...",
            angle="...",
            meta_description="...",
            # NO published_at, NO live_url — legacy pre-spec entry.
        )
    ]

    mock_output = MeasurementBriefOutput(actions=[], article_verdicts=[], coverage_note="")

    with patch("agents.measurement_agent.load_calendar", AsyncMock(return_value=entries)), \
         patch("agents.measurement_agent.gsc_client") as mock_gsc, \
         patch("agents.measurement_agent.ga4_client") as mock_ga4, \
         patch("agents.measurement_agent.get_dfs_client") as mock_get_dfs, \
         patch("agents.measurement_agent.get_llm") as mock_get_llm, \
         patch("agents.measurement_agent.file_service.read_text", AsyncMock(return_value="facts")):

        mock_gsc.query_blog_performance = AsyncMock(return_value=[])
        mock_ga4.query_blog_engagement = AsyncMock(return_value=([], {}))

        mock_dfs = MagicMock()
        mock_dfs.ranked_keywords_for_site = AsyncMock(return_value=[])
        mock_get_dfs.return_value = mock_dfs

        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_chain
        mock_get_llm.return_value = mock_llm

        final = await measurement_agent.run_measurement_agent(days=28)

    assert "legacy-article" in final.coverage_note
    assert "missing live_url" in final.coverage_note or "live_url/published_at" in final.coverage_note
    # Article must NOT silently appear in per_article — it should be skipped.
    assert final.report.per_article == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_measurement_agent.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the agent**

Create `agents/measurement_agent.py`:

```python
"""Measurement agent: GSC + GA4 + DFS Labs → MeasurementReport → LLM synthesis → FinalMeasurementReport.

Numbers are deterministic; only the prose interpretation goes through an LLM.
"""

import asyncio
from datetime import date, timedelta
from urllib.parse import urlparse

from langchain_core.prompts import ChatPromptTemplate

from models.article import ArticleStatus, ContentCalendarEntry
from models.measurement import (
    DataSourceStatus,
    FinalMeasurementReport,
    GapOpportunity,
    MeasurementReport,
    MetricScore,
    QueryRow,
    ScoredArticlePerformance,
    normalize_url,
    report_to_synthesis_input,
)
from output_schemas import MeasurementBriefOutput
from prompts.loader import load_prompt
from services import file_service, ga4_client, gsc_client
from services.calendar_service import load_calendar
from services.dataforseo_client import get_client as get_dfs_client
from services.llm import get_llm
from services.scoring import (
    Label,
    expected_ctr_for_position,
    score_cta_rate,
    score_ctr,
    score_engagement_time,
    score_impressions,
    score_position,
)


GSC_LAG_DAYS = 3   # See spec Section 5: GSC 'final' data lags ~2-3 days.


measurement_synthesis_prompt = load_prompt("chains/measurement_synthesis.md")


def _worst_label(labels: list[Label]) -> Label:
    """Roll up per-metric labels into an overall label. Worst wins; INSUFFICIENT_DATA
    is treated as missing (skipped) unless it's the only label."""
    if not labels:
        return Label.insufficient_data
    rank = {Label.poor: 3, Label.borderline: 2, Label.good: 1, Label.insufficient_data: 0}
    non_insufficient = [l for l in labels if l != Label.insufficient_data]
    if not non_insufficient:
        return Label.insufficient_data
    return max(non_insufficient, key=lambda l: rank[l])


def _format_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def _days_between(start: str, end_iso: date) -> int:
    return (end_iso - date.fromisoformat(start)).days


async def _safe_gsc(start, end):
    try:
        return await gsc_client.query_blog_performance(start, end), None
    except Exception as exc:  # noqa: BLE001
        return [], f"GSC fetch failed: {exc}"


async def _safe_ga4(start, end):
    """Returns ((rows, cta_by_path), error_message_or_none)."""
    try:
        rows, cta_by_path = await ga4_client.query_blog_engagement(start, end)
        return (rows, cta_by_path), None
    except Exception as exc:  # noqa: BLE001
        return ([], {}), f"GA4 fetch failed: {exc}"


async def _safe_dfs_ranked():
    try:
        client = get_dfs_client()
        rows = await client.ranked_keywords_for_site("draftandarc.com", url_substring="/blog/")
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], f"DataForSEO ranked-keywords fetch failed: {exc}"


def _aggregate_per_article(
    entries: list[ContentCalendarEntry],
    gsc_rows: list[dict],
    ga4_rows: list[dict],
    ga4_cta_by_path: dict[str, int],
    end_iso: date,
) -> tuple[list[ScoredArticlePerformance], list[str]]:
    """Join GSC + GA4 rows to calendar entries on exact normalized live_url.

    Returns (per_article, coverage_skipped_ids). Caller is expected to surface
    any skipped ids in DataSourceStatus.notes so they don't silently disappear
    from the brief.

    URL matching is intentionally asymmetric:
      - GSC returns FULL URLs in the 'page' field (host + path) → join on
        normalize_url(r["page"]) == normalize_url(entry.live_url).
      - GA4 returns only the path in 'page_path' → join on rstrip("/") of
        the path. Do NOT try to "unify" these — they're different upstream
        contracts.
    """
    out: list[ScoredArticlePerformance] = []
    coverage_skipped: list[str] = []

    for entry in entries:
        if entry.status != ArticleStatus.published:
            continue
        if not entry.live_url or not entry.published_at:
            coverage_skipped.append(entry.id)
            continue

        target_url = normalize_url(entry.live_url)
        # GSC join on full URL.
        gsc_for_article = [r for r in gsc_rows if normalize_url(r["page"]) == target_url]
        # GA4 join on pagePath only (different upstream contract — see docstring).
        target_path = urlparse(target_url).path
        ga4_for_article = [r for r in ga4_rows if r["page_path"].rstrip("/") == target_path]

        days_since = _days_between(entry.published_at, end_iso)

        impressions = sum(r["impressions"] for r in gsc_for_article)
        clicks = sum(r["clicks"] for r in gsc_for_article)
        avg_position = (
            sum(r["position"] * r["impressions"] for r in gsc_for_article) / impressions
            if impressions else 0.0
        )
        ctr = clicks / impressions if impressions else 0.0

        users = sum(r["active_users"] for r in ga4_for_article)
        avg_engagement = (
            sum(r["avg_session_duration"] * r["active_users"] for r in ga4_for_article) / users
            if users else 0.0
        )
        # CTA is attributed per-path, looked up in the separate dict from ga4_client.
        # Looking up under the same target_path the engagement join used.
        cta_clicks = ga4_cta_by_path.get(target_path, 0)

        metrics = {
            "position": MetricScore(
                value=avg_position,
                display=f"pos {avg_position:.1f}",
                label=score_position(avg_position) if impressions else Label.insufficient_data,
                reason="page 1 sweet spot is 1-3" if avg_position < 3.5 else
                       ("on page 1" if avg_position < 10.5 else "page 2"),
            ),
            "ctr": MetricScore(
                value=ctr,
                display=f"{ctr * 100:.1f}%",
                label=score_ctr(ctr, avg_position) if impressions else Label.insufficient_data,
                reason=(
                    f"vs ~{expected_ctr_for_position(avg_position):.1%} expected at this position"
                    if impressions else "no impressions yet"
                ),
            ),
            "impressions": MetricScore(
                value=impressions,
                display=f"{impressions}",
                label=score_impressions(impressions, days_since),
                reason=("not yet 14 days post-publish" if days_since < 14 else
                        "100+ in 28d is healthy"),
            ),
            "engagement": MetricScore(
                value=avg_engagement,
                display=_format_duration(avg_engagement) if users else "no data",
                label=score_engagement_time(avg_engagement) if users else Label.insufficient_data,
                reason="2:00+ = actually read",
            ),
            "cta_rate": MetricScore(
                value=cta_clicks / users if users else 0.0,
                display=f"{cta_clicks}/{users}" if users else "no users",
                label=score_cta_rate(cta_clicks, users),
                reason="industry baseline 1-3%",
            ),
        }

        overall = _worst_label([m.label for m in metrics.values()])

        # Top queries: pick top 5 by impressions.
        top_queries = [
            QueryRow(
                query=r["query"], impressions=r["impressions"], clicks=r["clicks"],
                ctr=r["ctr"], position=r["position"],
            )
            for r in sorted(gsc_for_article, key=lambda x: x["impressions"], reverse=True)[:5]
        ]

        out.append(ScoredArticlePerformance(
            article_id=entry.id,
            url=entry.live_url,
            published_at=entry.published_at,
            days_since_publish=days_since,
            overall_label=overall,
            metrics=metrics,
            top_queries=top_queries,
        ))

    return out, coverage_skipped


def _gap_opportunities(
    entries: list[ContentCalendarEntry],
    dfs_ranked: list[dict],
) -> list[GapOpportunity]:
    """Keywords we rank for that we didn't target.

    Targeted set = primary + secondary across all calendar entries.
    Lowercased on both sides for the diff.
    """
    targeted: set[str] = set()
    for e in entries:
        targeted.add(e.primary_keyword.lower().strip())
        for kw in e.secondary_keywords:
            targeted.add(kw.lower().strip())

    out: list[GapOpportunity] = []
    for row in dfs_ranked:
        kw = (row.get("keyword") or "").lower().strip()
        if not kw or kw in targeted:
            continue
        out.append(GapOpportunity(
            keyword=row["keyword"],
            position=float(row.get("position", 0)),
            volume=int(row.get("volume", 0)),
            url=row.get("url", ""),
        ))
    # Sort by potential: low position + high volume first.
    out.sort(key=lambda g: (g.position, -g.volume))
    return out


async def run_measurement_agent(days: int = 28) -> FinalMeasurementReport:
    """Pull GSC + GA4 + DFS Labs data, score per-article metrics, synthesize via LLM."""
    end = date.today() - timedelta(days=GSC_LAG_DAYS)
    start = end - timedelta(days=days)

    entries = await load_calendar()

    # Parallel fetch. GA4 result is a (rows, cta_by_path) tuple.
    (gsc_rows, gsc_err), (ga4_result, ga4_err), (dfs_rows, dfs_err) = await asyncio.gather(
        _safe_gsc(start, end),
        _safe_ga4(start, end),
        _safe_dfs_ranked(),
    )
    ga4_rows, ga4_cta_by_path = ga4_result

    notes: list[str] = []
    if gsc_err: notes.append(gsc_err)
    if ga4_err: notes.append(ga4_err)
    if dfs_err: notes.append(dfs_err)

    per_article, skipped_ids = _aggregate_per_article(
        entries, gsc_rows, ga4_rows, ga4_cta_by_path, end
    )
    if skipped_ids:
        notes.append(
            f"{len(skipped_ids)} published article(s) missing live_url/published_at "
            f"and skipped: {', '.join(skipped_ids)}. "
            f"Run --mark-published <id> --url <live_url> to include."
        )

    status = DataSourceStatus(
        gsc_ok=gsc_err is None,
        ga4_ok=ga4_err is None,
        dfs_ok=dfs_err is None,
        notes=notes,
    )

    gap_opps = _gap_opportunities(entries, dfs_rows)

    headline = {
        "articles": len(per_article),
        "impressions": sum(r["impressions"] for r in gsc_rows),
        "clicks": sum(r["clicks"] for r in gsc_rows),
        "ctr": (sum(r["clicks"] for r in gsc_rows) / max(1, sum(r["impressions"] for r in gsc_rows))),
        "avg_position": (
            sum(r["position"] * r["impressions"] for r in gsc_rows)
            / max(1, sum(r["impressions"] for r in gsc_rows))
        ),
    }

    report = MeasurementReport(
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        headline=headline,
        per_article=per_article,
        gap_opportunities=gap_opps,
        data_source_status=status,
    )

    # LLM synthesis.
    product_facts = ""
    try:
        product_facts = await file_service.read_text(file_service.PRODUCT_FACTS_PATH)
    except Exception:
        pass

    chain = measurement_synthesis_prompt | get_llm().with_structured_output(
        MeasurementBriefOutput, method="function_calling"
    )
    synthesis_input = report_to_synthesis_input(report)
    output: MeasurementBriefOutput = await chain.ainvoke({
        "raw_data": synthesis_input,
        "product_facts": product_facts,
    })

    # Belt-and-suspenders: enforce article_id validity.
    valid_ids = {a.article_id for a in per_article}
    verdicts = {v.article_id: v.verdict for v in output.article_verdicts if v.article_id in valid_ids}

    # Spec Section 6: deterministic data_source_status.notes must be prepended
    # to the final coverage_note so a failed source / skipped article can't be
    # softened or omitted by the LLM.
    coverage_parts: list[str] = []
    if status.notes:
        coverage_parts.append("Data-source / coverage notes (deterministic):")
        for note in status.notes:
            coverage_parts.append(f"  - {note}")
    if output.coverage_note:
        coverage_parts.append(output.coverage_note)
    final_coverage_note = "\n".join(coverage_parts)

    return FinalMeasurementReport(
        report=report,
        actions=list(output.actions),
        verdicts=verdicts,
        coverage_note=final_coverage_note,
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_measurement_agent.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/measurement_agent.py tests/test_measurement_agent.py
git commit -m "feat: add measurement_agent — deterministic aggregation + LLM synthesis

Parallel fetch of GSC + GA4 + DFS Labs. Per-article rollups joined on
exact normalized live_url. Scoring via services/scoring.py. LLM
produces only verdicts + actions + coverage_note (no numbers).
Per-source failures degrade gracefully via DataSourceStatus notes."
```

---

## Task 29: Add `--mode measure` to `main.py` + orchestrator entry

**Files:**
- Modify: `agents/orchestrator.py`
- Modify: `main.py`

- [ ] **Step 1: Add `run_measure` to orchestrator**

Append to `agents/orchestrator.py`:

```python
async def run_measure(days: int = 28) -> tuple[Path, Path]:
    """Run the measurement pipeline; write MD + HTML briefs. Returns the two paths."""
    from agents.measurement_agent import run_measurement_agent
    from renderers.measurement_md import render_md
    from renderers.measurement_html import render_html
    from services import file_service
    from services.dataforseo_client import get_client as get_dfs_client

    try:
        final = await run_measurement_agent(days=days)

        md = render_md(final)
        effective_note = "data finalized through " + final.report.window_end
        html = render_html(final, effective_end_note=effective_note)

        await file_service.atomic_write_text(file_service.MEASUREMENT_BRIEF_MD_PATH, md)
        await file_service.atomic_write_text(file_service.MEASUREMENT_BRIEF_HTML_PATH, html)
    finally:
        # Close the httpx AsyncClient on the singleton DFS client to avoid
        # 'unclosed transport' RuntimeWarning on process exit.
        try:
            await get_dfs_client().aclose()
        except Exception:  # noqa: BLE001
            pass

    return file_service.MEASUREMENT_BRIEF_MD_PATH, file_service.MEASUREMENT_BRIEF_HTML_PATH
```

- [ ] **Step 2: Wire into `main.py`**

Open `main.py`. Update the parser:

```python
parser.add_argument(
    "--mode",
    choices=["setup", "weekly", "article", "validate", "measure"],
    required=False,
    help="setup | weekly | article | validate | measure",
)
parser.add_argument(
    "--days",
    type=int,
    default=28,
    help="Days of measurement data to include (default: 28). Used with --mode measure.",
)
```

Add the handler:

```python
async def _run_measure(days: int) -> None:
    from agents.orchestrator import run_measure
    md_path, html_path = await run_measure(days=days)
    print(f"\nMeasurement brief written:")
    print(f"  Agent-facing (MD):  {md_path}")
    print(f"  Human dashboard:    {html_path}")
```

In `main()` dispatch:

```python
    elif args.mode == "measure":
        asyncio.run(_run_measure(args.days))
```

- [ ] **Step 3: Smoke-test (best-effort)**

If your `.env` is fully configured with DFS + GSC + GA4 credentials and you have at least one published calendar entry:
```bash
uv run python main.py --mode measure --days 28
```
Expected: prints two paths, both files exist. Without credentials, expect a clean error from one of the safe-fetch helpers; the run shouldn't crash hard.

- [ ] **Step 4: Commit**

```bash
git add agents/orchestrator.py main.py
git commit -m "feat: add --mode measure + run_measure orchestrator entry"
```

---

## Task 30: Wire measurement brief into orchestrator's SEO agent context

**Files:**
- Modify: `agents/orchestrator.py`
- Create: `tests/test_orchestrator_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_orchestrator_wiring.py`:

```python
"""Orchestrator appends measurement_brief.md to SEO agent context when present."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_run_weekly_batch_includes_measurement_brief_when_present(tmp_path: Path):
    from agents import orchestrator
    from services import file_service

    measurement_brief_content = "## Measurement Brief — 2026-05-19\n- impressions: 800\n"
    brief_path = tmp_path / "measurement_brief.md"
    brief_path.write_text(measurement_brief_content, encoding="utf-8")

    captured_context: dict = {}

    async def fake_run_seo_agent(context: str, existing_ids: set):
        captured_context["text"] = context
        return []

    with patch.object(file_service, "MEASUREMENT_BRIEF_MD_PATH", brief_path), \
         patch.object(file_service, "PRODUCT_FACTS_PATH", tmp_path / "product_facts.md"), \
         patch.object(file_service, "COMPETITOR_PROFILES_PATH", tmp_path / "competitors.md"), \
         patch.object(file_service, "MARKET_BRIEF_PATH", tmp_path / "market_brief.md"), \
         patch.object(orchestrator, "run_setup_research", AsyncMock(return_value=("facts", "competitors"))), \
         patch.object(orchestrator, "run_market_research", AsyncMock(return_value="market brief content")), \
         patch.object(orchestrator, "run_seo_agent", side_effect=fake_run_seo_agent), \
         patch.object(orchestrator.calendar_service, "load_calendar", AsyncMock(return_value=[])), \
         patch.object(orchestrator.calendar_service, "add_entries", AsyncMock()):

        # Pre-populate the files file_service tries to read.
        (tmp_path / "product_facts.md").write_text("facts")
        (tmp_path / "competitors.md").write_text("competitors")

        await orchestrator.run_weekly_batch()

    assert "## MEASUREMENT BRIEF" in captured_context["text"]
    assert measurement_brief_content in captured_context["text"]


async def test_run_weekly_batch_omits_measurement_brief_when_missing(tmp_path: Path):
    from agents import orchestrator
    from services import file_service

    captured_context: dict = {}

    async def fake_run_seo_agent(context: str, existing_ids: set):
        captured_context["text"] = context
        return []

    with patch.object(file_service, "MEASUREMENT_BRIEF_MD_PATH", tmp_path / "missing.md"), \
         patch.object(file_service, "PRODUCT_FACTS_PATH", tmp_path / "product_facts.md"), \
         patch.object(file_service, "COMPETITOR_PROFILES_PATH", tmp_path / "competitors.md"), \
         patch.object(file_service, "MARKET_BRIEF_PATH", tmp_path / "market_brief.md"), \
         patch.object(orchestrator, "run_setup_research", AsyncMock(return_value=("facts", "competitors"))), \
         patch.object(orchestrator, "run_market_research", AsyncMock(return_value="market brief content")), \
         patch.object(orchestrator, "run_seo_agent", side_effect=fake_run_seo_agent), \
         patch.object(orchestrator.calendar_service, "load_calendar", AsyncMock(return_value=[])), \
         patch.object(orchestrator.calendar_service, "add_entries", AsyncMock()):

        (tmp_path / "product_facts.md").write_text("facts")
        (tmp_path / "competitors.md").write_text("competitors")

        await orchestrator.run_weekly_batch()

    assert "MEASUREMENT BRIEF" not in captured_context["text"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_orchestrator_wiring.py -v`
Expected: FAIL.

- [ ] **Step 3: Update `run_weekly_batch`**

Open `agents/orchestrator.py`. Update `run_weekly_batch`:

```python
async def run_weekly_batch() -> list[str]:
    """Refresh market data + plan 4 articles. Returns planned article titles."""
    if not file_service.PRODUCT_FACTS_PATH.exists() or not file_service.COMPETITOR_PROFILES_PATH.exists():
        await run_setup()

    competitor_profiles = await file_service.read_text(file_service.COMPETITOR_PROFILES_PATH)
    market_brief = await run_market_research(competitor_profiles)
    await file_service.write_text(file_service.MARKET_BRIEF_PATH, market_brief)

    existing = await calendar_service.load_calendar()
    existing_ids = {e.id for e in existing}

    research_context = competitor_profiles + "\n\n" + market_brief

    # Append measurement brief if it exists. The delimiter is structural —
    # the SEO system prompt's PAST-PERFORMANCE CONTEXT section looks for this exact header.
    if file_service.MEASUREMENT_BRIEF_MD_PATH.exists():
        measurement_brief = await file_service.read_text(file_service.MEASUREMENT_BRIEF_MD_PATH)
        research_context += "\n\n## MEASUREMENT BRIEF\n\n" + measurement_brief

    new_entries = await run_seo_agent(research_context, existing_ids)
    await calendar_service.add_entries(new_entries)

    return [e.title for e in new_entries]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_orchestrator_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/orchestrator.py tests/test_orchestrator_wiring.py
git commit -m "feat: wire measurement brief into SEO agent context

Orchestrator prepends '## MEASUREMENT BRIEF' delimiter and appends
the brief when present. Graceful when missing (first run)."
```

---

## Task 31: Add `PAST-PERFORMANCE CONTEXT` section to SEO system prompt

**Files:**
- Modify: `prompts/md/agents/seo_system.md`

- [ ] **Step 1: Append the section**

Open `prompts/md/agents/seo_system.md`. Add at the end of the file:

```markdown

# PAST-PERFORMANCE CONTEXT (when available)

The research context may include a `## MEASUREMENT BRIEF` section showing how previously-published articles performed. When present, treat it as priority signal:

- **"Recommended actions"** in the brief — treat as your highest-priority candidates. If the brief says "follow-up on X" or "refresh Y", surface those before generating net-new ideas.
- **High-performing articles** (good position, good CTR) — propose adjacent or follow-up topics. Success is the strongest signal you have.
- **"Domain-level gap opportunities"** — keywords we rank for but didn't target. These are usually easy wins: a real ranking already exists, so a properly-targeted article often jumps to page 1.
- **0-impression articles** — do NOT propose retargeting the same keyword. The angle was wrong or competition was too strong. Either way, don't double down without a different angle.

If no `## MEASUREMENT BRIEF` section is in the context, proceed as before — this is normal for the first weekly batch.
```

- [ ] **Step 2: Confirm prompt still loads**

Run: `uv run python -c "from prompts.loader import load_system_prompt; print(load_system_prompt('agents/seo_system.md')[-100:])"`
Expected: prints the last ~100 characters of the file (no error).

- [ ] **Step 3: Commit**

```bash
git add prompts/md/agents/seo_system.md
git commit -m "feat: teach SEO agent to use the measurement brief in context"
```

---

## Task 32: Add `measure` and `validate` targets to the Makefile

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Update the Makefile**

Replace `Makefile` with:

```make
.PHONY: install test setup weekly article measure validate

install:
	uv sync

test:
	uv run pytest

setup:
	uv run python main.py --mode setup

weekly:
	uv run python main.py --mode weekly

article:
	uv run python main.py --mode article

measure:
	uv run python main.py --mode measure

validate:
	uv run python main.py --mode validate
```

- [ ] **Step 2: Verify**

Run: `make -n measure`
Expected: prints `uv run python main.py --mode measure` (no execution).

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add make measure and make validate targets"
```

---

## Task 33: Create `docs/playbooks/seo/00-overview.md`

**Why fully written:** This is the entry point — every other doc cross-links here. Needed before the implementer ships.

**Files:**
- Create: `docs/playbooks/seo/00-overview.md`

- [ ] **Step 1: Create the directory**

Run: `mkdir -p docs/playbooks/seo`

- [ ] **Step 2: Write the doc**

Create `docs/playbooks/seo/00-overview.md`:

```markdown
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
Last updated: 2026-05-20
```

- [ ] **Step 3: Commit**

```bash
git add docs/playbooks/seo/00-overview.md
git commit -m "docs: add SEO playbook overview"
```

---

## Task 34: Create `01-fundamentals.md` (fully written)

**Files:**
- Create: `docs/playbooks/seo/01-fundamentals.md`

- [ ] **Step 1: Write the doc**

Create `docs/playbooks/seo/01-fundamentals.md`:

```markdown
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
Last updated: 2026-05-20
```

- [ ] **Step 2: Commit**

```bash
git add docs/playbooks/seo/01-fundamentals.md
git commit -m "docs: add SEO fundamentals playbook"
```

---

## Task 35: Create `02-keyword-strategy.md` (outline + first sections)

**Why partial:** Real examples want real data. After one cycle of running `measure`, you'll have actual SERP observations to write the worked examples from. Until then, the doc is structured with placeholders explicitly flagged.

**Files:**
- Create: `docs/playbooks/seo/02-keyword-strategy.md`

- [ ] **Step 1: Write the doc**

Create `docs/playbooks/seo/02-keyword-strategy.md`:

```markdown
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
Last updated: 2026-05-20
```

- [ ] **Step 2: Commit**

```bash
git add docs/playbooks/seo/02-keyword-strategy.md
git commit -m "docs: add keyword strategy playbook (outline, examples deferred)"
```

---

## Task 36: Create `03-dataforseo-cheatsheet.md` (fully written)

**Files:**
- Create: `docs/playbooks/seo/03-dataforseo-cheatsheet.md`

- [ ] **Step 1: Write the doc**

Create `docs/playbooks/seo/03-dataforseo-cheatsheet.md`:

```markdown
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
Last updated: 2026-05-20
```

- [ ] **Step 2: Commit**

```bash
git add docs/playbooks/seo/03-dataforseo-cheatsheet.md
git commit -m "docs: add DataForSEO endpoint cheatsheet"
```

---

## Task 37: Create `04-measurement-cheatsheet.md` (outline + first sections)

**Files:**
- Create: `docs/playbooks/seo/04-measurement-cheatsheet.md`

- [ ] **Step 1: Write the doc**

Create `docs/playbooks/seo/04-measurement-cheatsheet.md`:

```markdown
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
Last updated: 2026-05-20
```

- [ ] **Step 2: Commit**

```bash
git add docs/playbooks/seo/04-measurement-cheatsheet.md
git commit -m "docs: add measurement cheatsheet (thresholds, actions deferred)"
```

---

## Task 38: Create `05-gsc-ga4-setup.md` (fully written)

**Files:**
- Create: `docs/playbooks/seo/05-gsc-ga4-setup.md`

- [ ] **Step 1: Write the doc**

Create `docs/playbooks/seo/05-gsc-ga4-setup.md`:

```markdown
# GSC + GA4 Service Account Setup

One-time setup for the measurement layer. ~15 minutes if you've used Google Cloud before; 30 minutes the first time.

## Prerequisites

- Owner-level access to the Google Search Console property for `draftandarc.com`.
- Edit-level access to the GA4 property for `draftandarc.com`.
- A Google account that can create a new Google Cloud project.

## Step-by-step

### 1. Create a Google Cloud project

1. Go to `console.cloud.google.com`.
2. Click the project dropdown (top left) → "New Project".
3. Name it `draftandarc-seo-measurement`. Leave organization blank if you don't have one.
4. Click "Create" and wait ~30 seconds.

### 2. Enable the two APIs

In the new project, go to "APIs & Services" → "Library".

1. Search for "Google Search Console API". Click it. Click "Enable".
2. Search for "Google Analytics Data API". Click it. Click "Enable".

(You do NOT need the Google Analytics Admin API — we deliberately avoided that dependency.)

### 3. Create a service account

1. Go to "IAM & Admin" → "Service Accounts" → "Create Service Account".
2. Name: `seo-measurement`. The email auto-fills as `seo-measurement@draftandarc-seo-measurement.iam.gserviceaccount.com`.
3. Skip the "grant access to project" step (we grant access *to GSC/GA4*, not to the GCP project).
4. Click "Done".
5. On the service account list, click the new account → "Keys" tab → "Add Key" → "Create new key" → "JSON".
6. The browser downloads `draftandarc-seo-measurement-XXXXX.json`. Move it to `~/.config/draftandarc/gcp-service-account.json`:
   ```bash
   mkdir -p ~/.config/draftandarc
   mv ~/Downloads/draftandarc-seo-measurement-*.json ~/.config/draftandarc/gcp-service-account.json
   ```

### 4. Grant the service account access to Search Console

1. Go to `search.google.com/search-console`.
2. Open settings (gear icon, bottom left) → "Users and permissions".
3. Click "Add user".
4. User email: the service account email from step 3 (`seo-measurement@draftandarc-seo-measurement.iam.gserviceaccount.com`).
5. Permission: **Restricted**. (Don't grant Full — least privilege. If `--mode validate` later returns a permission error from GSC, come back and upgrade to Full as the recovery step.)
6. Click "Add".

### 5. Grant the service account access to GA4

1. Go to `analytics.google.com`.
2. Bottom-left gear icon (admin).
3. In the "Property" column, click "Property access management".
4. Click "+" → "Add users".
5. Email: same service account email.
6. Role: **Viewer**.
7. Click "Add".

### 6. Note the GA4 property ID

Still in GA4 → Admin → Property settings → "Property details" → "PROPERTY ID" is a 9-or-10-digit number (e.g., `123456789`).

### 7. Populate `.env`

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/Users/<you>/.config/draftandarc/gcp-service-account.json
GSC_SITE_URL=sc-domain:draftandarc.com
GA4_PROPERTY_ID=123456789
```

### 8. Validate

```bash
uv run python main.py --mode validate
```

Expected: three `[PASS]` lines, one per integration. If any FAILs, re-check the corresponding grant step.

## Recovery: "I lost my service account JSON"

The JSON is a private key — Google won't regenerate the same one. To recover:

1. Go to GCP → IAM & Admin → Service Accounts → the service account → Keys.
2. Create a new key (same flow as step 3.5 above). Save to the same path.
3. The old key remains valid until you delete it; delete it from the Keys list to be safe.

No re-grants needed in GSC or GA4 — the service account email didn't change.

---
Last updated: 2026-05-20
```

- [ ] **Step 2: Commit**

```bash
git add docs/playbooks/seo/05-gsc-ga4-setup.md
git commit -m "docs: add GSC + GA4 service-account setup playbook"
```

---

## Task 39: Create `06-when-to-refresh-vs-rewrite-vs-kill.md` (outline + first sections)

**Files:**
- Create: `docs/playbooks/seo/06-when-to-refresh-vs-rewrite-vs-kill.md`

- [ ] **Step 1: Write the doc**

Create `docs/playbooks/seo/06-when-to-refresh-vs-rewrite-vs-kill.md`:

```markdown
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
Last updated: 2026-05-20
```

- [ ] **Step 2: Commit**

```bash
git add docs/playbooks/seo/06-when-to-refresh-vs-rewrite-vs-kill.md
git commit -m "docs: add refresh/rewrite/kill decision playbook"
```

---

## Task 40: Create `CLAUDE.md`

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write the file**

Create `CLAUDE.md`:

```markdown
# CLAUDE.md

Project: AI Learning Subagents — marketing-agent system for Draft and Arc.

## What this is

A multi-agent system that researches market opportunities, plans SEO-optimized articles, drafts them, fact-checks them, opens PRs to the blog repo, and measures how published articles perform.

## Starting point for SEO context

Before doing SEO work, read `docs/playbooks/seo/00-overview.md`. It points at the rest of the playbook.

## Key invariants

- The `tools/` package re-exports the research-agent's legacy tools (`jina_reader`, `tavily_search_tool`, `list_codebase_files`, `read_codebase_file`). New tools (e.g., DataForSEO) go in `tools/dataforseo.py`.
- All file writes that the system depends on (calendar JSON, measurement brief) go through `services.file_service.atomic_write_text`. Don't bypass this.
- The DataForSEO client is a process-scoped singleton (`services.dataforseo_client.get_client()`). The cost tracker on it enforces per-run caps.
- Measurement numbers are deterministic — they never go through an LLM. Only prose verdicts and action priorities are LLM-generated.

## Where to read next

- Design spec: `docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md`
- Implementation plan: `docs/superpowers/plans/2026-05-20-seo-measurement-implementation.md`
- SEO playbook: `docs/playbooks/seo/00-overview.md`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md as the project context entry point"
```

---

## Task 41: Final smoke test + spec coverage check

**Files:** none

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS, no skips with hidden failures.

- [ ] **Step 2: Verify the four CLI modes exist**

Run:
```bash
uv run python main.py --help
```
Expected output mentions: `setup`, `weekly`, `article`, `validate`, `measure`, and `--mark-published`.

- [ ] **Step 3: Spec coverage walkthrough**

Open `docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md` and skim each numbered section. For each, point at the task(s) that implement it:

- Section 1 (Context) — no tasks needed; framing only.
- Section 2 (Decisions) — embodied in tool/file layout (Tasks 1, 21, all).
- Section 3 (Architecture + Files) — Tasks 1, 3, 5, 16, 22, 24, 32 cover file additions/changes.
- Section 4 (DataForSEO) — Tasks 5, 6, 7, 8, 9, 10, 11, 14.
- Section 5 (GSC + GA4) — Tasks 16, 17, 18, 19.
- Section 6 (`--mode measure`) — Tasks 20, 21, 23, 24, 26, 27, 28, 29.
- Section 7 (Wiring) — Tasks 30, 31.
- Section 8 (Playbook) — Tasks 33–39.
- Section 9 (Testing + Guardrails) — embedded throughout. `--mode validate` covered by Tasks 12, 19.
- Section 10 (Limitations) — captured in `CLAUDE.md` (Task 40) and playbook docs.
- Section 11 (Summary) — no tasks needed.

If anything in the spec doesn't have a task above, stop and surface it before declaring done.

- [ ] **Step 4: Commit nothing (this task changes no files)**

This is the close-out gate. If steps 1–3 pass, the implementation matches the spec.

---

## Out of scope (deferred to follow-up specs/plans)

- Article-quality improvements (writing prompt upgrades, programming-specific patterns).
- Generation of the 10-article batch the user originally requested (5 on-demand topic-teasers + 5 standard with programming focus).
- Brief history directory (week-over-week comparison).
- Automated PR-merge → `--mark-published` trigger.
- `signup_cta_click` event implementation on the blog template.
- Fixing the pre-existing `gpt-5.4-mini` typo in `config.py`.
