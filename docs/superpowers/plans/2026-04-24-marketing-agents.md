# Draft and Arc Marketing Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a four-agent marketing system (Research, SEO, Writing, Orchestrator) that produces 2–4 grounded, SEO-optimized blog article drafts per week for Draft and Arc.

**Architecture:** Batch Pipeline with Shared Knowledge Store. Research and SEO agents run once per weekly batch and write results to files on disk (`data/`). The Writing agent processes one article at a time from a JSON content calendar. A Fact-Check LCEL pass runs after each draft before it reaches human review. All inter-agent communication is through typed Pydantic models and files — no live message passing.

**Tech Stack:** Python 3.12+, LangChain, LangGraph (`create_react_agent` for Research/SEO), LCEL with `with_structured_output(method="function_calling")` for Writing/Fact-Check, Pydantic v2, `pydantic-settings`, Tavily Search API, SerpAPI (People Also Ask), pytrends, Jina AI Reader (no key — HTTP GET), uv, pytest + pytest-asyncio.

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | `pydantic_settings.BaseSettings` — loads `.env`, exposes `settings` singleton |
| `output_schemas.py` | All LLM output Pydantic schemas (`_StrictModel` base, `extra="forbid"`) |
| `tools.py` | Four custom LangChain tools: Jina Reader, SerpAPI PAA, pytrends, codebase reader |
| `models/article.py` | `ArticleStatus`, `ArticleType`, `ContentCalendarEntry` |
| `models/research.py` | `Competitor`, `ProductFact`, `ContentOpportunity`, `ResearchBrief` |
| `models/seo.py` | `KeywordData`, `ArticlePlan` |
| `services/llm.py` | `get_llm()` — global singleton, mirrors main repo |
| `services/file_service.py` | Async read/write for `data/` files; exports path constants |
| `services/calendar_service.py` | `content_calendar.json` CRUD: load, save, add, next_planned, update_status |
| `prompts/loader.py` | `load_prompt(filename)` — splits `.md` on `---HUMAN---` into `ChatPromptTemplate` |
| `prompts/md/research_synthesis.md` | Prompt for synthesising raw research data into structured output |
| `prompts/md/seo_synthesis.md` | Prompt for synthesising keyword research into article plans |
| `prompts/md/writing.md` | Prompt for writing one article draft |
| `prompts/md/fact_check.md` | Prompt for fact-checking a draft against `product_facts.md` |
| `prompts/research.py` | Exports `research_synthesis_prompt` and `RESEARCH_AGENT_SYSTEM_PROMPT` |
| `prompts/seo.py` | Exports `seo_synthesis_prompt` and `SEO_AGENT_SYSTEM_PROMPT` |
| `prompts/writing.py` | Exports `writing_prompt` |
| `prompts/fact_check.py` | Exports `fact_check_prompt` |
| `chains/writing_chain.py` | LCEL: `writing_prompt \| get_llm().with_structured_output(ArticleOutput)` |
| `chains/fact_check_chain.py` | LCEL: `fact_check_prompt \| get_llm().with_structured_output(FactCheckOutput)` |
| `agents/research_agent.py` | `create_react_agent` loop + synthesis LCEL step → writes `product_facts.md` + `research_brief.md` |
| `agents/seo_agent.py` | `create_react_agent` loop + synthesis LCEL step → returns `list[ContentCalendarEntry]` |
| `agents/writing_agent.py` | Calls writing chain → saves draft markdown file |
| `agents/orchestrator.py` | Sequences all agents; manages article lifecycle in calendar |
| `main.py` | CLI: `--mode weekly \| article` |
| `tests/conftest.py` | Shared fixtures: `tmp_data_dir`, `sample_calendar_entry`, `sample_product_facts` |
| `tests/test_models.py` | Pydantic validation tests for all domain models and output schemas |
| `tests/test_services.py` | Async tests for file_service and calendar_service using `tmp_path` |
| `tests/test_chains.py` | Writing + fact-check chain tests with mocked LLM |
| `tests/test_agents.py` | Agent tests with mocked LLM, tools, and chains |

---

## Task 1: Project Setup

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`, `data/.gitkeep`, `data/drafts/.gitkeep`
- Modify: `.gitignore`
- Create: `tests/__init__.py`, `models/__init__.py`, `services/__init__.py`, `prompts/__init__.py`, `chains/__init__.py`, `agents/__init__.py`, `prompts/md/.gitkeep`

- [ ] **Step 1: Update pyproject.toml with dependencies and pytest config**

Replace the entire `pyproject.toml`:

```toml
[project]
name = "ai-learning-subagents"
version = "0.1.0"
description = "Multi-agent marketing system for Draft and Arc"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "langchain-community>=0.3",
    "langgraph>=0.2",
    "tavily-python>=0.3",
    "google-search-results>=2.4",
    "pytrends>=4.9",
    "pydantic-settings>=2.0",
    "aiofiles>=24.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `.env.example`**

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY=tvly-...
SERPAPI_API_KEY=...
CODEBASE_PATH=/Users/ilirgruda/Repo/Python/ai-learning
```

- [ ] **Step 3: Update `.gitignore`**

Add these lines to `.gitignore`:
```
.env
data/*.md
data/*.json
data/drafts/
!data/.gitkeep
!data/drafts/.gitkeep
```

- [ ] **Step 4: Create all package `__init__.py` files and data directories**

```bash
touch tests/__init__.py models/__init__.py services/__init__.py \
      prompts/__init__.py chains/__init__.py agents/__init__.py
mkdir -p prompts/md data/drafts
touch data/.gitkeep data/drafts/.gitkeep prompts/md/.gitkeep
```

- [ ] **Step 5: Install dependencies**

```bash
uv sync --dev
```

Expected: resolves and installs all packages with no errors.

- [ ] **Step 6: Verify pytest runs (no tests yet)**

```bash
uv run pytest --collect-only
```

Expected: `no tests ran` — no errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example .gitignore tests/ models/ services/ prompts/ chains/ agents/ data/
git commit -m "feat: project setup — deps, package structure, data dirs"
```

---

## Task 2: Domain Models

**Files:**
- Create: `models/article.py`, `models/research.py`, `models/seo.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for domain models**

Create `tests/test_models.py`:

```python
import pytest
from models.article import ArticleStatus, ArticleType, ContentCalendarEntry
from models.research import Competitor, ProductFact, ContentOpportunity, ResearchBrief
from models.seo import KeywordData, ArticlePlan


def test_content_calendar_entry_defaults():
    entry = ContentCalendarEntry(
        id="test-slug",
        title="How to Learn Anything Fast",
        primary_keyword="learn anything fast",
        article_type=ArticleType.standard,
        target_audience="curious learners",
        angle="timeframe personalisation beats generic courses",
        meta_description="A 150-char meta description.",
        cta_prompt="",
    )
    assert entry.status == ArticleStatus.planned
    assert entry.secondary_keywords == []
    assert entry.suggested_headings == []
    assert entry.draft_path is None


def test_content_calendar_entry_status_progression():
    entry = ContentCalendarEntry(
        id="slug",
        title="T",
        primary_keyword="kw",
        article_type=ArticleType.topic_teaser,
        target_audience="a",
        angle="b",
        meta_description="c",
        cta_prompt="prompt",
    )
    assert entry.status == ArticleStatus.planned
    entry.status = ArticleStatus.in_progress
    assert entry.status == ArticleStatus.in_progress


def test_research_brief_defaults():
    brief = ResearchBrief()
    assert brief.competitors == []
    assert brief.pain_points == []
    assert brief.content_opportunities == []


def test_competitor_model():
    c = Competitor(
        name="Duolingo",
        url="https://duolingo.com",
        positioning="gamified language learning",
        target_audience="casual language learners",
        content_gaps=["personalised timeframes", "non-language topics"],
    )
    assert c.name == "Duolingo"
    assert len(c.content_gaps) == 2


def test_keyword_data_model():
    kw = KeywordData(
        keyword="how to learn Spanish in 30 days",
        intent="informational",
        competition_level="low",
        trend="rising",
    )
    assert kw.competition_level == "low"


def test_article_plan_round_trips_to_dict():
    plan = ArticlePlan(
        id="learn-spanish-30-days",
        title="How to Learn Spanish in 30 Days",
        primary_keyword="learn Spanish fast",
        secondary_keywords=["Spanish for beginners"],
        search_intent="informational",
        article_type="topic_teaser",
        target_audience="beginners",
        angle="Draft and Arc generates a personalised Spanish course in seconds",
        meta_description="Learn Spanish in 30 days with a personalised plan.",
        suggested_headings=["H2: Why 30 days works", "H2: The plan"],
        cta_prompt="Create a 30-day beginner Spanish course for me",
    )
    d = plan.model_dump()
    assert d["id"] == "learn-spanish-30-days"
    ArticlePlan(**d)  # round-trips without error
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_models.py -v
```

Expected: `ImportError` — modules don't exist yet.

- [ ] **Step 3: Create `models/article.py`**

```python
from enum import StrEnum
from typing import Optional
from pydantic import BaseModel


class ArticleStatus(StrEnum):
    planned = "planned"
    in_progress = "in_progress"
    ready_for_review = "ready_for_review"
    needs_review_flagged = "needs_review_flagged"
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
    draft_path: Optional[str] = None
```

- [ ] **Step 4: Create `models/research.py`**

```python
from pydantic import BaseModel


class Competitor(BaseModel):
    name: str
    url: str
    positioning: str
    target_audience: str
    content_gaps: list[str] = []


class ProductFact(BaseModel):
    fact: str
    source_file: str


class ContentOpportunity(BaseModel):
    angle: str
    rationale: str
    target_audience: str


class ResearchBrief(BaseModel):
    competitors: list[Competitor] = []
    pain_points: list[str] = []
    content_opportunities: list[ContentOpportunity] = []
```

- [ ] **Step 5: Create `models/seo.py`**

```python
from pydantic import BaseModel


class KeywordData(BaseModel):
    keyword: str
    intent: str
    competition_level: str  # low | medium | high
    trend: str              # rising | stable | falling


class ArticlePlan(BaseModel):
    id: str
    title: str
    primary_keyword: str
    secondary_keywords: list[str] = []
    search_intent: str = "informational"
    article_type: str
    target_audience: str
    angle: str
    meta_description: str
    suggested_headings: list[str] = []
    cta_prompt: str = ""
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add models/ tests/test_models.py
git commit -m "feat: domain models — ContentCalendarEntry, ResearchBrief, ArticlePlan"
```

---

## Task 3: Config and LLM Singleton

**Files:**
- Create: `config.py`, `services/llm.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing test**

Create `tests/conftest.py`:

```python
import os
import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    (tmp_path / "drafts").mkdir()
    return tmp_path


@pytest.fixture
def sample_product_facts() -> str:
    return """## Draft and Arc — Product Facts

- Users create courses from a text prompt or by uploading a PDF
- Knowledge levels: beginner, intermediate, advanced
- Users set daily learning time (default: 20 minutes)
- Users set course duration in days (default: 14 days)
- Lesson types: concept, workshop, case_study, problem_set, project, deep_dive
- Learning domains: conceptual, procedural, technical, creative, physical, language, analytical
- Feynman technique: user explains a concept; AI scores and gives feedback
- Quiz assessments with multiple-choice questions and explanations
- Progress tracking: completed lessons, time spent per lesson
- Note-taking: one note per lesson per user
- Google OAuth login supported
- PDF upload: document is processed with RAG; lessons use it as context
"""


@pytest.fixture
def sample_calendar_entry():
    from models.article import ContentCalendarEntry, ArticleType
    return ContentCalendarEntry(
        id="feynman-technique-for-programmers",
        title="The Feynman Technique for Programmers: Learn Anything Faster",
        primary_keyword="feynman technique programming",
        secondary_keywords=["how to learn programming faster", "feynman method study"],
        article_type=ArticleType.standard,
        target_audience="developers who want to learn faster",
        angle="Draft and Arc's built-in Feynman prompts make this technique effortless",
        meta_description="Use the Feynman Technique to master any programming concept. Learn how it works and how to apply it today.",
        suggested_headings=[
            "H2: What is the Feynman Technique?",
            "H2: Why it works for technical concepts",
            "H2: How to apply it to programming",
            "H2: The shortcut",
        ],
        cta_prompt="Create a course that uses the Feynman Technique to teach me Python decorators",
    )
```

Add `tests/test_config.py`:

```python
import pytest


def test_settings_loads():
    """Settings must load without raising — requires .env or env vars."""
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
    os.environ.setdefault("SERPAPI_API_KEY", "serp-test")
    os.environ.setdefault("CODEBASE_PATH", "/tmp/fake-codebase")

    from config import settings
    assert settings.openai_model  # not empty
    assert settings.codebase_path


def test_get_llm_returns_singleton():
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
    os.environ.setdefault("SERPAPI_API_KEY", "serp-test")
    os.environ.setdefault("CODEBASE_PATH", "/tmp/fake-codebase")

    from services.llm import get_llm
    llm1 = get_llm()
    llm2 = get_llm()
    assert llm1 is llm2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ImportError` — `config` not defined.

- [ ] **Step 3: Create `config.py`**

```python
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(Path(__file__).parent / ".env")


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    tavily_api_key: str
    serpapi_api_key: str
    codebase_path: str = "/Users/ilirgruda/Repo/Python/ai-learning"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
```

- [ ] **Step 4: Create `services/llm.py`**

```python
from langchain_openai import ChatOpenAI
from config import settings

_llm: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )
    return _llm
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add config.py services/llm.py tests/conftest.py tests/test_config.py
git commit -m "feat: config (pydantic-settings) and LLM singleton"
```

---

## Task 4: Output Schemas

**Files:**
- Create: `output_schemas.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests — append to `tests/test_models.py`**

```python
from output_schemas import (
    _StrictModel,
    CompetitorOutput,
    ContentOpportunityOutput,
    ProductFactOutput,
    ResearchOutput,
    ArticlePlanOutput,
    SEOOutput,
    ArticleOutput,
    FactCheckItemOutput,
    FactCheckOutput,
)


def test_strict_model_rejects_extra_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CompetitorOutput(
            name="X",
            url="https://x.com",
            positioning="p",
            target_audience="a",
            content_gaps=[],
            unexpected_field="boom",
        )


def test_research_output_valid():
    output = ResearchOutput(
        competitors=[
            CompetitorOutput(
                name="Duolingo",
                url="https://duolingo.com",
                positioning="gamified",
                target_audience="casual",
                content_gaps=["no custom topics"],
            )
        ],
        pain_points=["no personalised pacing"],
        content_opportunities=[
            ContentOpportunityOutput(
                angle="Feynman technique for programmers",
                rationale="competitors don't cover this",
                target_audience="developers",
            )
        ],
        product_facts=[
            ProductFactOutput(
                fact="Users set daily learning time",
                source_file="app/models/course.py",
            )
        ],
    )
    assert len(output.competitors) == 1


def test_fact_check_output_passed():
    fc = FactCheckOutput(passed=True, items=[])
    assert fc.passed


def test_fact_check_output_flagged():
    fc = FactCheckOutput(
        passed=False,
        items=[
            FactCheckItemOutput(
                claim="Draft and Arc offers video lessons",
                verdict="UNSUPPORTED",
                source_sentence="Draft and Arc offers video lessons for visual learners.",
            )
        ],
    )
    assert not fc.passed
    assert fc.items[0].verdict == "UNSUPPORTED"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_models.py -v -k "strict or research_output or fact_check"
```

Expected: `ImportError` — `output_schemas` not defined.

- [ ] **Step 3: Create `output_schemas.py`**

```python
from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    """Base for all LLM output schemas — rejects extra fields from LLM."""
    model_config = ConfigDict(extra="forbid")


class CompetitorOutput(_StrictModel):
    name: str
    url: str
    positioning: str
    target_audience: str
    content_gaps: list[str]


class ContentOpportunityOutput(_StrictModel):
    angle: str
    rationale: str
    target_audience: str


class ProductFactOutput(_StrictModel):
    fact: str
    source_file: str


class ResearchOutput(_StrictModel):
    competitors: list[CompetitorOutput]
    pain_points: list[str]
    content_opportunities: list[ContentOpportunityOutput]
    product_facts: list[ProductFactOutput]


class ArticlePlanOutput(_StrictModel):
    id: str
    title: str
    primary_keyword: str
    secondary_keywords: list[str]
    search_intent: str
    article_type: str
    target_audience: str
    angle: str
    meta_description: str
    suggested_headings: list[str]
    cta_prompt: str


class SEOOutput(_StrictModel):
    articles: list[ArticlePlanOutput]


class ArticleOutput(_StrictModel):
    title: str
    primary_keyword: str
    meta_description: str
    markdown_content: str  # full article body in markdown


class FactCheckItemOutput(_StrictModel):
    claim: str
    verdict: str          # VERIFIED | UNSUPPORTED | CONTRADICTED
    source_sentence: str


class FactCheckOutput(_StrictModel):
    passed: bool
    items: list[FactCheckItemOutput]
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add output_schemas.py tests/test_models.py
git commit -m "feat: LLM output schemas with _StrictModel base"
```

---

## Task 5: File Service and Calendar Service

**Files:**
- Create: `services/file_service.py`, `services/calendar_service.py`
- Create: `tests/test_services.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_services.py`:

```python
import json
import pytest
from pathlib import Path
from models.article import ArticleStatus, ArticleType, ContentCalendarEntry


@pytest.fixture
def calendar_path(tmp_path: Path) -> Path:
    return tmp_path / "content_calendar.json"


@pytest.fixture
def entry() -> ContentCalendarEntry:
    return ContentCalendarEntry(
        id="test-article",
        title="Test Article",
        primary_keyword="test keyword",
        article_type=ArticleType.standard,
        target_audience="testers",
        angle="testing is good",
        meta_description="A test article.",
    )


# --- file_service ---

async def test_write_and_read_text(tmp_path: Path):
    from services.file_service import write_text, read_text
    p = tmp_path / "hello.md"
    await write_text(p, "# Hello")
    result = await read_text(p)
    assert result == "# Hello"


async def test_write_creates_parent_dirs(tmp_path: Path):
    from services.file_service import write_text
    p = tmp_path / "nested" / "deep" / "file.md"
    await write_text(p, "content")
    assert p.exists()


# --- calendar_service ---

async def test_load_empty_calendar(tmp_path: Path, monkeypatch):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    result = await calendar_service.load_calendar()
    assert result == []


async def test_add_and_load_entries(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    loaded = await calendar_service.load_calendar()
    assert len(loaded) == 1
    assert loaded[0].id == "test-article"


async def test_add_entries_deduplicates(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    await calendar_service.add_entries([entry])  # same id — should not duplicate
    loaded = await calendar_service.load_calendar()
    assert len(loaded) == 1


async def test_next_planned_returns_first_planned(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    result = await calendar_service.next_planned()
    assert result is not None
    assert result.id == "test-article"


async def test_next_planned_returns_none_when_empty(tmp_path: Path, monkeypatch):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    result = await calendar_service.next_planned()
    assert result is None


async def test_update_status(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    await calendar_service.update_status("test-article", ArticleStatus.in_progress)
    loaded = await calendar_service.load_calendar()
    assert loaded[0].status == ArticleStatus.in_progress


async def test_update_status_with_draft_path(tmp_path: Path, monkeypatch, entry: ContentCalendarEntry):
    from services import calendar_service
    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_path / "calendar.json")
    await calendar_service.add_entries([entry])
    await calendar_service.update_status(
        "test-article", ArticleStatus.ready_for_review, draft_path="data/drafts/draft.md"
    )
    loaded = await calendar_service.load_calendar()
    assert loaded[0].draft_path == "data/drafts/draft.md"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_services.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `services/file_service.py`**

```python
from pathlib import Path
import aiofiles

DATA_DIR = Path("data")
DRAFTS_DIR = DATA_DIR / "drafts"
RESEARCH_BRIEF_PATH = DATA_DIR / "research_brief.md"
PRODUCT_FACTS_PATH = DATA_DIR / "product_facts.md"


async def read_text(path: Path) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return await f.read()


async def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
```

- [ ] **Step 4: Create `services/calendar_service.py`**

```python
import json
from pathlib import Path
from typing import Optional
import aiofiles
from models.article import ArticleStatus, ContentCalendarEntry

CALENDAR_PATH = Path("data/content_calendar.json")


async def load_calendar() -> list[ContentCalendarEntry]:
    if not CALENDAR_PATH.exists():
        return []
    async with aiofiles.open(CALENDAR_PATH, "r", encoding="utf-8") as f:
        data = json.loads(await f.read())
    return [ContentCalendarEntry(**entry) for entry in data]


async def save_calendar(entries: list[ContentCalendarEntry]) -> None:
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(CALENDAR_PATH, "w", encoding="utf-8") as f:
        await f.write(json.dumps([e.model_dump() for e in entries], indent=2))


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
) -> None:
    entries = await load_calendar()
    for entry in entries:
        if entry.id == entry_id:
            entry.status = status
            if draft_path is not None:
                entry.draft_path = draft_path
    await save_calendar(entries)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_services.py -v
```

Expected: 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add services/file_service.py services/calendar_service.py tests/test_services.py
git commit -m "feat: file service and calendar service with full CRUD"
```

---

## Task 6: Prompt System

**Files:**
- Create: `prompts/loader.py`
- Create: `prompts/md/research_synthesis.md`, `prompts/md/seo_synthesis.md`, `prompts/md/writing.md`, `prompts/md/fact_check.md`
- Create: `prompts/research.py`, `prompts/seo.py`, `prompts/writing.py`, `prompts/fact_check.py`

This mirrors the main repo's `app/ai/prompts/loader.py` exactly.

- [ ] **Step 1: Create `prompts/loader.py`**

```python
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate

PROMPTS_DIR = Path(__file__).parent / "md"
SEPARATOR = "---HUMAN---"


def load_prompt(filename: str) -> ChatPromptTemplate:
    text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    parts = text.split(SEPARATOR, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(
            f"Prompt file '{filename}' must contain exactly one '{SEPARATOR}' separator."
        )
    system, human = parts
    return ChatPromptTemplate.from_messages([
        ("system", system.strip()),
        ("human", human.strip()),
    ])
```

- [ ] **Step 2: Create `prompts/md/research_synthesis.md`**

```markdown
You are the Research Agent for Draft and Arc, an AI-powered personalized learning platform.
You have just completed a research phase using tools. Now synthesize your findings into structured output.

PRODUCT FACTS RULES:
- Only include features you found in actual code files — never infer or guess
- Write facts as short, concrete statements: "Users set daily learning time (default: 20 minutes)"
- Include the source file for every fact
- Do NOT include features marked as TODO or out of scope in the code
- Known real features: course creation (prompt or PDF), knowledge levels (beginner/intermediate/advanced),
  daily learning time, course duration in days, lesson types (concept/workshop/case_study/problem_set/project/deep_dive),
  learning domains (conceptual/procedural/technical/creative/physical/language/analytical),
  Feynman technique, quiz assessments, progress tracking, time tracking, note-taking, Google OAuth,
  document RAG (PDF → vector search → lesson context)
- NOT included: video, audio, images, external resource links (marked out of scope in code)

COMPETITOR SEED LIST: alice.tech, 360Learning, Docebo, Sana Labs, Absorb LMS, Duolingo, Coursera, Pearson, Arist, 5Mins.ai
Always include competitors you discovered beyond this list.
---HUMAN---
CODEBASE PATH: {codebase_path}

RAW RESEARCH DATA GATHERED BY YOUR TOOLS:
{gathered_data}

Produce the full structured output now. Include all competitors found, all pain points,
all content opportunities, and all product facts extracted from the codebase.
```

- [ ] **Step 3: Create `prompts/md/seo_synthesis.md`**

```markdown
You are the SEO Agent for Draft and Arc. You have just gathered keyword and SERP data using tools.
Now synthesize your findings into exactly 4 article plans for this week's content calendar.

KEYWORD STRATEGY:
- Prioritize long-tail keywords (3+ words) with low competition
- Informational search intent only — readers learning, not buying
- Avoid head terms (online learning, e-learning) — unreachable for a new domain
- Mix article types: 2 standard (Feynman, personalised learning strategy) + 2 topic_teaser (how to learn X)
- Only recommend topics with stable or rising trend data
- id field: lowercase, hyphen-separated slug from the title

ARTICLE TYPES:
- standard: learning strategy, Feynman technique, study skills — ends with soft Draft and Arc CTA
- topic_teaser: "how to learn [topic] in [timeframe]" — ends with a direct course prompt CTA
---HUMAN---
RESEARCH BRIEF:
{research_brief}

EXISTING CALENDAR IDS (do not duplicate these topics):
{existing_ids}

RAW KEYWORD AND SERP DATA:
{gathered_data}

Produce exactly 4 article plans now. Each must have a unique id not in the existing calendar.
```

- [ ] **Step 4: Create `prompts/md/writing.md`**

```markdown
You are the Writing Agent for Draft and Arc, an AI-powered personalized learning platform.
You write one article at a time. Your job is to produce a draft that is accurate, engaging, and ready for human review.

BRAND VOICE:
Energetic and motivating. Short sentences. Short paragraphs. The reader should feel like they can actually do this.
Write like a smart, enthusiastic friend — not a marketer, not an academic.
No jargon without definition. No passive voice. No fluff. If a sentence doesn't earn its place, cut it.

GROUNDING RULE — non-negotiable:
You may ONLY claim Draft and Arc does something if it appears in the PRODUCT FACTS section below.
If a feature isn't listed, omit it or describe the category without a specific claim.
When in doubt, leave it out.

STRUCTURE:
- Hook: open with a tension or question the reader already feels (2–3 sentences)
- Body: follow the suggested headings, rewritten to sound human
- For topic_teaser: end with — "Want to go deeper? Try this on Draft and Arc: [cta_prompt]"
- For standard: end with one sentence pointing to Draft and Arc
- Target length: 900–1400 words. Punchy, not padded.

OUTPUT FORMAT:
Return the full article in the markdown_content field.
The title, primary_keyword, and meta_description fields must match the article plan exactly.
---HUMAN---
PRODUCT FACTS (ground all claims here — this is the only truth):
{product_facts}

ARTICLE PLAN:
Title: {title}
Primary keyword: {primary_keyword}
Secondary keywords: {secondary_keywords}
Article type: {article_type}
Target audience: {target_audience}
Angle: {angle}
Suggested headings: {suggested_headings}
CTA prompt (for topic_teaser only): {cta_prompt}
Meta description: {meta_description}

Write the article now.
```

- [ ] **Step 5: Create `prompts/md/fact_check.md`**

```markdown
You are a fact-checker for Draft and Arc marketing content.
You will receive two documents: verified product facts and a draft article.

For every claim the article makes about Draft and Arc (what the product does, features it has, how it works),
mark each claim as:
- VERIFIED: directly supported by the product facts
- UNSUPPORTED: not found anywhere in the product facts
- CONTRADICTED: conflicts with the product facts

Be precise. Only flag claims about Draft and Arc — not general claims about learning or study techniques.
If no claims are made about Draft and Arc, or all are verified, set passed=true and items=[].
---HUMAN---
PRODUCT FACTS:
{product_facts}

DRAFT ARTICLE:
{draft_content}

List every Draft and Arc claim with its verdict now.
```

- [ ] **Step 6: Create the four prompt module files**

`prompts/research.py`:
```python
from prompts.loader import load_prompt

RESEARCH_AGENT_SYSTEM_PROMPT = """You are the Research Agent for Draft and Arc, an AI-powered personalized learning platform.
Your job is to gather comprehensive information about the product and the market using your tools.

TOOLS AVAILABLE:
- read_codebase_file: read a specific file from the Draft and Arc codebase
- list_codebase_files: list Python files in the codebase
- jina_reader: read the text content of any URL
- tavily_search: search the web for information

WORKFLOW:
1. Read the codebase: start with app/models/ and app/ai/ to extract real product features
2. Read competitor pages: use jina_reader on each competitor's homepage and features page
3. Search for market pain points: use tavily_search to find forums and reviews
4. When you have gathered enough data, respond with a summary of ALL findings.

Be thorough. Be accurate. Never guess about product features."""

research_synthesis_prompt = load_prompt("research_synthesis.md")
```

`prompts/seo.py`:
```python
from prompts.loader import load_prompt

SEO_AGENT_SYSTEM_PROMPT = """You are the SEO Agent for Draft and Arc. You research keywords and plan articles.

TOOLS AVAILABLE:
- tavily_search: search the web and see what's ranking for a keyword
- people_also_ask: get People Also Ask questions from Google for a query
- google_trends: check if interest in a keyword is rising, stable, or falling

WORKFLOW:
1. Read the research brief to understand content opportunities
2. For each opportunity, use tavily_search to see existing content and competition level
3. Use people_also_ask to find real user questions (long-tail keyword gold)
4. Use google_trends to verify interest is stable or rising
5. When you have data for 4+ article ideas, respond with a summary of ALL findings.

Target long-tail, low-competition, informational queries only."""

seo_synthesis_prompt = load_prompt("seo_synthesis.md")
```

`prompts/writing.py`:
```python
from prompts.loader import load_prompt

writing_prompt = load_prompt("writing.md")
```

`prompts/fact_check.py`:
```python
from prompts.loader import load_prompt

fact_check_prompt = load_prompt("fact_check.md")
```

- [ ] **Step 7: Verify prompts load without error**

```bash
uv run python -c "
from prompts.research import research_synthesis_prompt, RESEARCH_AGENT_SYSTEM_PROMPT
from prompts.seo import seo_synthesis_prompt, SEO_AGENT_SYSTEM_PROMPT
from prompts.writing import writing_prompt
from prompts.fact_check import fact_check_prompt
print('All prompts loaded OK')
print('Writing prompt variables:', writing_prompt.input_variables)
"
```

Expected output:
```
All prompts loaded OK
Writing prompt variables: ['article_type', 'angle', 'cta_prompt', 'meta_description', 'primary_keyword', 'product_facts', 'secondary_keywords', 'suggested_headings', 'title']
```

- [ ] **Step 8: Commit**

```bash
git add prompts/
git commit -m "feat: prompt system — loader, 4 markdown templates, 4 prompt modules"
```

---

## Task 7: Custom LangChain Tools

**Files:**
- Create: `tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tools.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_jina_reader_returns_text():
    from tools import jina_reader
    mock_response = MagicMock()
    mock_response.text = "# Competitor Homepage\n\nWe offer X and Y."
    mock_response.raise_for_status = MagicMock()

    with patch("tools.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await jina_reader.ainvoke({"url": "https://example.com"})
        assert "Competitor Homepage" in result


def test_google_trends_rising():
    from tools import google_trends
    import pandas as pd
    mock_df = pd.DataFrame({"test keyword": [10, 10, 20, 20, 30, 30]})

    with patch("tools.TrendReq") as mock_trend_cls:
        mock_trend = MagicMock()
        mock_trend_cls.return_value = mock_trend
        mock_trend.interest_over_time.return_value = mock_df

        result = google_trends.invoke({"keyword": "test keyword"})
        assert result == "rising"


def test_google_trends_no_data():
    from tools import google_trends
    import pandas as pd

    with patch("tools.TrendReq") as mock_trend_cls:
        mock_trend = MagicMock()
        mock_trend_cls.return_value = mock_trend
        mock_trend.interest_over_time.return_value = pd.DataFrame()

        result = google_trends.invoke({"keyword": "obscure keyword"})
        assert result == "no_data"


def test_list_codebase_files(tmp_path):
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
    os.environ.setdefault("SERPAPI_API_KEY", "serp-test")

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "models.py").write_text("# models")
    (tmp_path / "app" / "__pycache__").mkdir()

    from tools import list_codebase_files
    with patch("tools.settings") as mock_settings:
        mock_settings.codebase_path = str(tmp_path)
        result = list_codebase_files.invoke({"directory": "app"})
        assert "models.py" in result
        assert "__pycache__" not in result


def test_read_codebase_file(tmp_path):
    (tmp_path / "test_file.py").write_text("x = 1")
    from tools import read_codebase_file
    with patch("tools.settings") as mock_settings:
        mock_settings.codebase_path = str(tmp_path)
        result = read_codebase_file.invoke({"relative_path": "test_file.py"})
        assert "x = 1" in result


def test_read_codebase_file_not_found(tmp_path):
    from tools import read_codebase_file
    with patch("tools.settings") as mock_settings:
        mock_settings.codebase_path = str(tmp_path)
        result = read_codebase_file.invoke({"relative_path": "missing.py"})
        assert "not found" in result.lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `tools.py`**

```python
from pathlib import Path
import httpx
from langchain_core.tools import tool
from pytrends.request import TrendReq
from config import settings


@tool
async def jina_reader(url: str) -> str:
    """Read the text content of any URL using Jina AI Reader. Use for competitor pages."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"https://r.jina.ai/{url}")
        response.raise_for_status()
        return response.text


@tool
def google_trends(keyword: str) -> str:
    """Check Google Trends interest for a keyword. Returns: rising, stable, falling, or no_data."""
    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload([keyword], timeframe="today 12-m")
    df = pytrends.interest_over_time()
    if df.empty or keyword not in df.columns:
        return "no_data"
    values = df[keyword].tolist()
    mid = len(values) // 2
    first_half = sum(values[:mid]) or 1
    second_half = sum(values[mid:]) or 0
    if second_half > first_half * 1.1:
        return "rising"
    if second_half < first_half * 0.9:
        return "falling"
    return "stable"


@tool
def people_also_ask(query: str) -> str:
    """Get People Also Ask questions from Google for a query. Best source of long-tail keywords."""
    from serpapi import GoogleSearch
    search = GoogleSearch({"q": query, "api_key": settings.serpapi_api_key})
    results = search.get_dict()
    questions = [q.get("question", "") for q in results.get("related_questions", [])[:10]]
    if not questions:
        return "No People Also Ask results found."
    return "\n".join(questions)


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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools.py tests/test_tools.py
git commit -m "feat: custom LangChain tools — Jina Reader, pytrends, SerpAPI PAA, codebase reader"
```

---

## Task 8: Writing and Fact-Check Chains

**Files:**
- Create: `chains/writing_chain.py`, `chains/fact_check_chain.py`
- Create: `tests/test_chains.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_chains.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from models.article import ArticleType, ContentCalendarEntry


@pytest.fixture
def entry(sample_calendar_entry) -> ContentCalendarEntry:
    return sample_calendar_entry


async def test_writing_chain_returns_article_output(entry, sample_product_facts):
    from output_schemas import ArticleOutput
    from chains.writing_chain import run_writing_chain

    mock_output = ArticleOutput(
        title=entry.title,
        primary_keyword=entry.primary_keyword,
        meta_description=entry.meta_description,
        markdown_content="# The Feynman Technique\n\nYou can learn anything...",
    )

    with patch("chains.writing_chain.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = MagicMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        # Patch the LCEL pipe so we can intercept
        with patch("chains.writing_chain.writing_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = await run_writing_chain(entry, sample_product_facts)

    assert result.title == entry.title
    assert "Feynman" in result.markdown_content


async def test_fact_check_chain_passes_clean_draft(sample_product_facts):
    from output_schemas import FactCheckOutput
    from chains.fact_check_chain import run_fact_check_chain

    mock_output = FactCheckOutput(passed=True, items=[])
    clean_draft = "The Feynman Technique is a study method. Try it today."

    with patch("chains.fact_check_chain.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = MagicMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        with patch("chains.fact_check_chain.fact_check_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = await run_fact_check_chain(sample_product_facts, clean_draft)

    assert result.passed is True
    assert result.items == []


async def test_fact_check_chain_flags_unsupported_claim(sample_product_facts):
    from output_schemas import FactCheckOutput, FactCheckItemOutput
    from chains.fact_check_chain import run_fact_check_chain

    mock_output = FactCheckOutput(
        passed=False,
        items=[
            FactCheckItemOutput(
                claim="Draft and Arc offers video lessons",
                verdict="UNSUPPORTED",
                source_sentence="Draft and Arc offers video lessons for visual learners.",
            )
        ],
    )
    bad_draft = "Draft and Arc offers video lessons for visual learners."

    with patch("chains.fact_check_chain.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = MagicMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        with patch("chains.fact_check_chain.fact_check_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = await run_fact_check_chain(sample_product_facts, bad_draft)

    assert result.passed is False
    assert result.items[0].verdict == "UNSUPPORTED"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_chains.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `chains/writing_chain.py`**

```python
from output_schemas import ArticleOutput
from prompts.writing import writing_prompt
from services.llm import get_llm
from models.article import ContentCalendarEntry


async def run_writing_chain(entry: ContentCalendarEntry, product_facts: str) -> ArticleOutput:
    chain = writing_prompt | get_llm().with_structured_output(ArticleOutput, method="function_calling")
    result: ArticleOutput = await chain.ainvoke({
        "product_facts": product_facts,
        "title": entry.title,
        "primary_keyword": entry.primary_keyword,
        "secondary_keywords": ", ".join(entry.secondary_keywords),
        "article_type": entry.article_type,
        "target_audience": entry.target_audience,
        "angle": entry.angle,
        "suggested_headings": "\n".join(entry.suggested_headings),
        "cta_prompt": entry.cta_prompt,
        "meta_description": entry.meta_description,
    })
    return result
```

- [ ] **Step 4: Create `chains/fact_check_chain.py`**

```python
from output_schemas import FactCheckOutput
from prompts.fact_check import fact_check_prompt
from services.llm import get_llm


async def run_fact_check_chain(product_facts: str, draft_content: str) -> FactCheckOutput:
    chain = fact_check_prompt | get_llm().with_structured_output(FactCheckOutput, method="function_calling")
    result: FactCheckOutput = await chain.ainvoke({
        "product_facts": product_facts,
        "draft_content": draft_content,
    })
    return result
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_chains.py -v
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add chains/ tests/test_chains.py
git commit -m "feat: writing chain and fact-check chain (LCEL + structured output)"
```

---

## Task 9: Research Agent

**Files:**
- Create: `agents/research_agent.py`
- Modify: `tests/test_agents.py` (create)

- [ ] **Step 1: Write failing test**

Create `tests/test_agents.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


async def test_research_agent_returns_product_facts_and_brief():
    from agents.research_agent import run_research_agent

    gathered_data = "Codebase: courses have knowledge_level, daily_minutes. Competitor Duolingo: gamified language app."

    fake_gather_result = {"messages": [AIMessage(content=gathered_data)]}

    from output_schemas import ResearchOutput, CompetitorOutput, ContentOpportunityOutput, ProductFactOutput
    fake_synthesis = ResearchOutput(
        competitors=[
            CompetitorOutput(
                name="Duolingo",
                url="https://duolingo.com",
                positioning="gamified language",
                target_audience="casual learners",
                content_gaps=["no custom topics"],
            )
        ],
        pain_points=["no personalised pacing"],
        content_opportunities=[
            ContentOpportunityOutput(
                angle="Feynman technique",
                rationale="gap in competitor content",
                target_audience="programmers",
            )
        ],
        product_facts=[
            ProductFactOutput(
                fact="Users set daily learning time (default: 20 minutes)",
                source_file="app/models/course.py",
            )
        ],
    )

    with patch("agents.research_agent.create_react_agent") as mock_create:
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_gather_result)
        mock_create.return_value = mock_agent

        with patch("agents.research_agent.get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=fake_synthesis)
            mock_llm.with_structured_output.return_value = mock_llm
            mock_llm_fn.return_value = mock_llm

            with patch("agents.research_agent.research_synthesis_prompt") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                product_facts, research_brief = await run_research_agent("/fake/codebase")

    assert "Users set daily learning time" in product_facts
    assert "Duolingo" in research_brief
    assert "Feynman technique" in research_brief
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_agents.py::test_research_agent_returns_product_facts_and_brief -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add `tavily_search_tool` to `tools.py`** (must exist before the agent imports it)

Append to `tools.py`:

```python
from langchain_community.tools.tavily_search import TavilySearchResults

tavily_search_tool = TavilySearchResults(max_results=5)
```

- [ ] **Step 4: Create `agents/research_agent.py`**

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from output_schemas import ResearchOutput
from prompts.research import RESEARCH_AGENT_SYSTEM_PROMPT, research_synthesis_prompt
from services.llm import get_llm
from tools import jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file


def _format_product_facts(output: ResearchOutput) -> str:
    lines = ["## Draft and Arc — Product Facts\n"]
    for fact in output.product_facts:
        lines.append(f"- {fact.fact}  *(source: {fact.source_file})*")
    return "\n".join(lines)


def _format_research_brief(output: ResearchOutput) -> str:
    sections = ["## Draft and Arc — Research Brief\n"]

    sections.append("### Competitor Analysis\n")
    for c in output.competitors:
        sections.append(f"**{c.name}** ({c.url})")
        sections.append(f"- Positioning: {c.positioning}")
        sections.append(f"- Target audience: {c.target_audience}")
        sections.append(f"- Content gaps: {', '.join(c.content_gaps)}\n")

    sections.append("### Market Pain Points\n")
    for pain in output.pain_points:
        sections.append(f"- {pain}")

    sections.append("\n### Content Opportunities\n")
    for opp in output.content_opportunities:
        sections.append(f"**{opp.angle}**")
        sections.append(f"- Why: {opp.rationale}")
        sections.append(f"- Audience: {opp.target_audience}\n")

    return "\n".join(sections)


async def run_research_agent(codebase_path: str) -> tuple[str, str]:
    """Run the research agent. Returns (product_facts_md, research_brief_md)."""
    tools = [jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=RESEARCH_AGENT_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=f"Research the product codebase at {codebase_path} and all competitors. Gather all data now.")]
    })
    gathered_data = result["messages"][-1].content

    chain = research_synthesis_prompt | get_llm().with_structured_output(ResearchOutput, method="function_calling")
    output: ResearchOutput = await chain.ainvoke({
        "codebase_path": codebase_path,
        "gathered_data": gathered_data,
    })

    return _format_product_facts(output), _format_research_brief(output)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_agents.py::test_research_agent_returns_product_facts_and_brief -v
```

Expected: 1 test passes.

- [ ] **Step 6: Commit**

```bash
git add agents/research_agent.py tools.py tests/test_agents.py
git commit -m "feat: research agent — create_react_agent + LCEL synthesis step"
```

---

## Task 10: SEO Agent

**Files:**
- Create: `agents/seo_agent.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing test — append to `tests/test_agents.py`**

```python
async def test_seo_agent_returns_calendar_entries():
    from agents.seo_agent import run_seo_agent
    from models.article import ArticleType

    gathered_data = "PAA: how to learn Spanish fast. Trend: rising. Competition: low."

    fake_gather_result = {"messages": [AIMessage(content=gathered_data)]}

    from output_schemas import SEOOutput, ArticlePlanOutput
    fake_synthesis = SEOOutput(articles=[
        ArticlePlanOutput(
            id="learn-spanish-30-days",
            title="How to Learn Spanish in 30 Days",
            primary_keyword="learn Spanish fast",
            secondary_keywords=["Spanish for beginners"],
            search_intent="informational",
            article_type="topic_teaser",
            target_audience="beginners",
            angle="personalized pacing beats Duolingo streaks",
            meta_description="Learn Spanish in 30 days with a personalised plan.",
            suggested_headings=["H2: Why 30 days works"],
            cta_prompt="Create a 30-day beginner Spanish course for me",
        ),
        ArticlePlanOutput(
            id="feynman-technique-study",
            title="The Feynman Technique: Learn Anything by Teaching It",
            primary_keyword="feynman technique study",
            secondary_keywords=[],
            search_intent="informational",
            article_type="standard",
            target_audience="self-directed learners",
            angle="Draft and Arc builds Feynman prompts into every lesson",
            meta_description="Master any subject with the Feynman Technique.",
            suggested_headings=["H2: What is Feynman Technique"],
            cta_prompt="",
        ),
        ArticlePlanOutput(
            id="learn-python-2-weeks",
            title="How to Learn Python in 2 Weeks",
            primary_keyword="learn python fast",
            secondary_keywords=[],
            search_intent="informational",
            article_type="topic_teaser",
            target_audience="beginners",
            angle="daily 20-minute sessions with a structured syllabus",
            meta_description="Learn Python in 2 weeks with a daily plan.",
            suggested_headings=["H2: The 2-week plan"],
            cta_prompt="Create a 2-week beginner Python course for me",
        ),
        ArticlePlanOutput(
            id="personalized-learning-plan",
            title="How to Build a Personalised Learning Plan",
            primary_keyword="personalized learning plan",
            secondary_keywords=[],
            search_intent="informational",
            article_type="standard",
            target_audience="self-improvers",
            angle="timeframe and daily minutes are the two variables that matter",
            meta_description="Build a personalised learning plan that actually works.",
            suggested_headings=["H2: Start with time"],
            cta_prompt="",
        ),
    ])

    research_brief = "Competitors: Duolingo, Coursera. Pain points: no personalised pacing."

    with patch("agents.seo_agent.create_react_agent") as mock_create:
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_gather_result)
        mock_create.return_value = mock_agent

        with patch("agents.seo_agent.get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=fake_synthesis)
            mock_llm.with_structured_output.return_value = mock_llm
            mock_llm_fn.return_value = mock_llm

            with patch("agents.seo_agent.seo_synthesis_prompt") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                entries = await run_seo_agent(research_brief, existing_ids=set())

    assert len(entries) == 4
    assert entries[0].id == "learn-spanish-30-days"
    assert entries[0].article_type == ArticleType.topic_teaser
    assert entries[1].article_type == ArticleType.standard
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_agents.py::test_seo_agent_returns_calendar_entries -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `agents/seo_agent.py`**

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from models.article import ArticleType, ContentCalendarEntry
from output_schemas import SEOOutput
from prompts.seo import SEO_AGENT_SYSTEM_PROMPT, seo_synthesis_prompt
from services.llm import get_llm
from tools import tavily_search_tool, people_also_ask, google_trends


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
    )


async def run_seo_agent(research_brief: str, existing_ids: set[str]) -> list[ContentCalendarEntry]:
    """Run the SEO agent. Returns 4 new ContentCalendarEntry items."""
    tools = [tavily_search_tool, people_also_ask, google_trends]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=SEO_AGENT_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=(
            f"Research keywords and SERP data for 4 article ideas. "
            f"Avoid these existing topics: {existing_ids or 'none'}. "
            "Use People Also Ask and Google Trends to validate each idea."
        ))]
    })
    gathered_data = result["messages"][-1].content

    chain = seo_synthesis_prompt | get_llm().with_structured_output(SEOOutput, method="function_calling")
    output: SEOOutput = await chain.ainvoke({
        "research_brief": research_brief,
        "existing_ids": ", ".join(existing_ids) if existing_ids else "none",
        "gathered_data": gathered_data,
    })

    return [_to_calendar_entry(plan) for plan in output.articles]
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_agents.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agents/seo_agent.py tests/test_agents.py
git commit -m "feat: SEO agent — create_react_agent + LCEL synthesis → ContentCalendarEntry list"
```

---

## Task 11: Writing Agent

**Files:**
- Create: `agents/writing_agent.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing tests — append to `tests/test_agents.py`**

```python
async def test_writing_agent_saves_draft(tmp_data_dir, sample_calendar_entry, sample_product_facts):
    from agents.writing_agent import run_writing_agent
    from output_schemas import ArticleOutput

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# The Feynman Technique\n\nYou can learn anything...",
    )

    with patch("agents.writing_agent.run_writing_chain", new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = fake_article
        with patch("agents.writing_agent.DRAFTS_DIR", tmp_data_dir / "drafts"):
            draft_path, article = await run_writing_agent(sample_calendar_entry, sample_product_facts)

    assert draft_path.exists()
    content = draft_path.read_text()
    assert "title:" in content
    assert "The Feynman Technique" in content
    assert article.markdown_content == fake_article.markdown_content


def test_remove_em_dashes_space_both_sides():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("learning — which") == "learning, which"


def test_remove_em_dashes_no_spaces():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("learning—which") == "learning, which"


def test_remove_em_dashes_space_before_only():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("learning —which") == "learning, which"


def test_remove_em_dashes_multiple():
    from agents.writing_agent import _remove_em_dashes
    result = _remove_em_dashes("fast — effective — proven")
    assert result == "fast, effective, proven"


def test_remove_em_dashes_no_emdash():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("no emdash here") == "no emdash here"


async def test_writing_agent_strips_em_dashes_from_saved_draft(tmp_data_dir, sample_calendar_entry, sample_product_facts):
    from agents.writing_agent import run_writing_agent
    from output_schemas import ArticleOutput

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="Learn fast — and remember more — every day.",
    )

    with patch("agents.writing_agent.run_writing_chain", new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = fake_article
        with patch("agents.writing_agent.DRAFTS_DIR", tmp_data_dir / "drafts"):
            draft_path, _ = await run_writing_agent(sample_calendar_entry, sample_product_facts)

    content = draft_path.read_text()
    assert "—" not in content
    assert "Learn fast, and remember more, every day." in content
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_agents.py -k "writing_agent or em_dash" -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `agents/writing_agent.py`**

```python
import re
from datetime import datetime
from pathlib import Path

from chains.writing_chain import run_writing_chain
from models.article import ContentCalendarEntry
from output_schemas import ArticleOutput
from services.file_service import DRAFTS_DIR, write_text


def _remove_em_dashes(text: str) -> str:
    """Replace em dashes (with any surrounding spaces) with a comma and single space."""
    return re.sub(r'\s*—\s*', ', ', text)


def _build_frontmatter(article: ArticleOutput) -> str:
    return (
        "---\n"
        f"title: {article.title}\n"
        f"primary_keyword: {article.primary_keyword}\n"
        f"meta_description: {article.meta_description}\n"
        "status: draft\n"
        "---\n\n"
    )


async def run_writing_agent(
    entry: ContentCalendarEntry,
    product_facts: str,
) -> tuple[Path, ArticleOutput]:
    """Write one article. Returns (draft_path, ArticleOutput)."""
    article = await run_writing_chain(entry, product_facts)

    clean_content = _remove_em_dashes(article.markdown_content)

    slug = entry.id
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}-{slug}.md"
    draft_path = DRAFTS_DIR / filename

    full_content = _build_frontmatter(article) + clean_content
    await write_text(draft_path, full_content)

    return draft_path, article
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_agents.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agents/writing_agent.py tests/test_agents.py
git commit -m "feat: writing agent — calls writing chain, saves markdown draft with frontmatter"
```

---

## Task 12: Orchestrator + Research Agent Split + Prompts Kick-off

**Design change from original plan:** Research Agent is split into two functions with different cadences. Prompts kick-off messages move to `prompts/` modules. Three CLI modes instead of two.

**Files:**
- Modify: `output_schemas.py` — add `ResearchSetupOutput`, `MarketBriefOutput`
- Modify: `services/file_service.py` — add `COMPETITOR_PROFILES_PATH`, `MARKET_BRIEF_PATH`; remove `RESEARCH_BRIEF_PATH`
- Create: `prompts/md/research_setup_synthesis.md`, `prompts/md/research_market_synthesis.md`
- Modify: `prompts/research.py` — split prompts + add kick-off constants
- Modify: `prompts/seo.py` — add SEO kick-off constant
- Modify: `agents/research_agent.py` — split into `run_setup_research()` + `run_market_research()`
- Modify: `agents/seo_agent.py` — use kick-off constant from prompts
- Create: `agents/orchestrator.py`
- Modify: `tests/test_agents.py` — update research agent tests + add orchestrator tests

---

**Step 1: Add two new output schemas to `output_schemas.py` (append):**

```python
class ResearchSetupOutput(_StrictModel):
    product_facts: list[ProductFactOutput]
    competitors: list[CompetitorOutput]


class MarketBriefOutput(_StrictModel):
    pain_points: list[str]
    content_opportunities: list[ContentOpportunityOutput]
```

**Step 2: Update `services/file_service.py` — add new paths, remove old `RESEARCH_BRIEF_PATH`:**

```python
from pathlib import Path
import aiofiles

DATA_DIR = Path("data")
DRAFTS_DIR = DATA_DIR / "drafts"
PRODUCT_FACTS_PATH = DATA_DIR / "product_facts.md"
COMPETITOR_PROFILES_PATH = DATA_DIR / "competitor_profiles.md"
MARKET_BRIEF_PATH = DATA_DIR / "market_brief.md"


async def read_text(path: Path) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return await f.read()


async def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
```

**Step 3: Create `prompts/md/research_setup_synthesis.md`:**

```
You are synthesising the results of a setup research session for Draft and Arc.
You have gathered data about the product codebase and competitor pages.

PRODUCT FACTS RULES:
- Only include features found in actual code files — never infer or guess
- Write facts as short, concrete statements: "Users set daily learning time (default: 20 minutes)"
- Include the source file for every fact
- Do NOT include features marked as TODO or out of scope in the code
- NOT included: video, audio, images, external resource links (marked out of scope in code)

COMPETITOR PROFILE RULES:
- One profile per competitor actually found/crawled
- Include: name, url, positioning, target_audience, content_gaps
- content_gaps: specific topics or angles the competitor does NOT cover well
---HUMAN---
CODEBASE PATH: {codebase_path}

RAW DATA GATHERED:
{gathered_data}

Produce the full structured output now. Include all product facts found in the codebase and all competitor profiles crawled.
```

**Step 4: Create `prompts/md/research_market_synthesis.md`:**

```
You are synthesising the results of a market research session for Draft and Arc.
You have searched for current user pain points, market trends, and content opportunities.

PAIN POINTS: what users complain about with existing learning tools — specific, sourced from real discussions.
CONTENT OPPORTUNITIES: specific angles where Draft and Arc can rank and stand out — tied to real pain points and competitor gaps.
---HUMAN---
COMPETITOR CONTEXT:
{competitor_profiles}

RAW MARKET DATA GATHERED:
{gathered_data}

Produce the full structured output now. Pain points should be concrete user complaints. Content opportunities should be specific and actionable.
```

**Step 5: Rewrite `prompts/research.py`:**

```python
from prompts.loader import load_prompt

RESEARCH_SETUP_SYSTEM_PROMPT = """You are the Setup Research Agent for Draft and Arc, an AI-powered personalized learning platform.
Your job: extract verified product facts from the codebase AND build competitor profiles by crawling their pages.

TOOLS AVAILABLE:
- read_codebase_file: read a specific file from the Draft and Arc codebase
- list_codebase_files: list Python files in the codebase to discover what to read
- jina_reader: read the text content of any URL (for competitor pages)
- tavily_search: search the web to discover new competitors

WORKFLOW:
1. List and read app/models/, app/ai/chains/, app/routers/ — extract real features only
2. For each competitor in the seed list, use jina_reader on their homepage and features page
3. Search for new competitors in the AI-native personalized learning space
4. When done, summarise ALL findings.

Competitor seed list: alice.tech, 360Learning, Docebo, Sana Labs, Absorb LMS, Duolingo, Coursera, Pearson, Arist, 5Mins.ai
Never guess about product features. Only include what you read in the code."""

RESEARCH_SETUP_KICKOFF = (
    "Read the codebase at {codebase_path} and crawl all competitor pages. "
    "Extract product facts from the code and build profiles for all competitors."
)

RESEARCH_MARKET_SYSTEM_PROMPT = """You are the Market Research Agent for Draft and Arc.
Your job: find current user pain points with existing learning tools and identify content opportunities.

TOOLS AVAILABLE:
- tavily_search: search the web for forums, Reddit, reviews, and discussions

WORKFLOW:
1. Search for complaints and pain points about: online learning platforms, e-learning tools, Duolingo, Coursera, LMS tools
2. Search for trending questions in the self-directed learning and study skills space
3. Look for underserved content gaps — topics where existing content is thin or outdated
4. When done, summarise ALL findings.

Focus on what real users are saying right now — not general assumptions."""

RESEARCH_MARKET_KICKOFF = (
    "Search for current user pain points with learning tools and identify content opportunities "
    "in the personalized learning market. Use the competitor context provided."
)

research_setup_synthesis_prompt = load_prompt("research_setup_synthesis.md")
research_market_synthesis_prompt = load_prompt("research_market_synthesis.md")
```

**Step 6: Update `prompts/seo.py` — add kick-off constant:**

```python
from prompts.loader import load_prompt

SEO_AGENT_SYSTEM_PROMPT = """You are the SEO Agent for Draft and Arc. You research keywords and plan articles.

TOOLS AVAILABLE:
- tavily_search: search the web and see what's ranking for a keyword
- people_also_ask: get People Also Ask questions from Google for a query
- google_trends: check if interest in a keyword is rising, stable, or falling

WORKFLOW:
1. Read the research context to understand content opportunities and competitor gaps
2. For each opportunity, use tavily_search to see existing content and competition level
3. Use people_also_ask to find real user questions (long-tail keyword gold)
4. Use google_trends to verify interest is stable or rising
5. When you have data for 4+ article ideas, respond with a summary of ALL findings.

Target long-tail, low-competition, informational queries only."""

SEO_KICKOFF = (
    "Research keywords and SERP data for 4 article ideas based on the context provided. "
    "Avoid these existing topics: {existing_ids}. "
    "Use People Also Ask and Google Trends to validate each idea."
)

seo_synthesis_prompt = load_prompt("seo_synthesis.md")
```

**Step 7: Rewrite `agents/research_agent.py`:**

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from output_schemas import ResearchSetupOutput, MarketBriefOutput
from prompts.research import (
    RESEARCH_SETUP_SYSTEM_PROMPT, RESEARCH_SETUP_KICKOFF,
    RESEARCH_MARKET_SYSTEM_PROMPT, RESEARCH_MARKET_KICKOFF,
    research_setup_synthesis_prompt, research_market_synthesis_prompt,
)
from services.llm import get_llm
from tools import jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file


def _format_product_facts(output: ResearchSetupOutput) -> str:
    lines = ["## Draft and Arc — Product Facts\n"]
    for fact in output.product_facts:
        lines.append(f"- {fact.fact}  *(source: {fact.source_file})*")
    return "\n".join(lines)


def _format_competitor_profiles(output: ResearchSetupOutput) -> str:
    sections = ["## Competitor Profiles\n"]
    for c in output.competitors:
        sections.append(f"**{c.name}** ({c.url})")
        sections.append(f"- Positioning: {c.positioning}")
        sections.append(f"- Target audience: {c.target_audience}")
        sections.append(f"- Content gaps: {', '.join(c.content_gaps)}\n")
    return "\n".join(sections)


def _format_market_brief(output: MarketBriefOutput) -> str:
    sections = ["## Market Brief\n", "### Pain Points\n"]
    for pain in output.pain_points:
        sections.append(f"- {pain}")
    sections.append("\n### Content Opportunities\n")
    for opp in output.content_opportunities:
        sections.append(f"**{opp.angle}**")
        sections.append(f"- Why: {opp.rationale}")
        sections.append(f"- Audience: {opp.target_audience}\n")
    return "\n".join(sections)


async def run_setup_research(codebase_path: str) -> tuple[str, str]:
    """Extract product facts + build competitor profiles. Returns (product_facts_md, competitor_profiles_md)."""
    tools = [jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=RESEARCH_SETUP_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=RESEARCH_SETUP_KICKOFF.format(codebase_path=codebase_path))]
    })
    gathered_data = result["messages"][-1].content

    chain = research_setup_synthesis_prompt | get_llm().with_structured_output(ResearchSetupOutput, method="function_calling")
    output: ResearchSetupOutput = await chain.ainvoke({
        "codebase_path": codebase_path,
        "gathered_data": gathered_data,
    })

    return _format_product_facts(output), _format_competitor_profiles(output)


async def run_market_research(competitor_profiles: str) -> str:
    """Search for current pain points and content opportunities. Returns market_brief_md."""
    tools = [tavily_search_tool]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=RESEARCH_MARKET_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=RESEARCH_MARKET_KICKOFF)]
    })
    gathered_data = result["messages"][-1].content

    chain = research_market_synthesis_prompt | get_llm().with_structured_output(MarketBriefOutput, method="function_calling")
    output: MarketBriefOutput = await chain.ainvoke({
        "competitor_profiles": competitor_profiles,
        "gathered_data": gathered_data,
    })

    return _format_market_brief(output)
```

**Step 8: Update `agents/seo_agent.py` — use kick-off constant:**

In `run_seo_agent`, replace the hardcoded `HumanMessage` string with:

```python
from prompts.seo import SEO_AGENT_SYSTEM_PROMPT, SEO_KICKOFF, seo_synthesis_prompt

# replace the HumanMessage line with:
HumanMessage(content=SEO_KICKOFF.format(existing_ids=existing_ids or "none"))
```

**Step 9: Write failing orchestrator tests — append to `tests/test_agents.py`:**

```python
async def test_orchestrator_setup(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_setup
    from services import file_service

    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "COMPETITOR_PROFILES_PATH", tmp_data_dir / "competitor_profiles.md")

    with patch("agents.orchestrator.run_setup_research", new_callable=AsyncMock) as mock_setup:
        mock_setup.return_value = ("- Users set daily learning time", "**Duolingo** (duolingo.com)")
        await run_setup()

    assert (tmp_data_dir / "product_facts.md").exists()
    assert "Users set daily learning time" in (tmp_data_dir / "product_facts.md").read_text()
    assert (tmp_data_dir / "competitor_profiles.md").exists()


async def test_orchestrator_weekly_batch(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_weekly_batch
    from services import calendar_service, file_service

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "COMPETITOR_PROFILES_PATH", tmp_data_dir / "competitor_profiles.md")
    monkeypatch.setattr(file_service, "MARKET_BRIEF_PATH", tmp_data_dir / "market_brief.md")

    await file_service.write_text(tmp_data_dir / "product_facts.md", "- fact")
    await file_service.write_text(tmp_data_dir / "competitor_profiles.md", "**Duolingo**")

    from models.article import ArticleType, ContentCalendarEntry
    fake_entries = [
        ContentCalendarEntry(
            id=f"article-{i}", title=f"Article {i}", primary_keyword=f"kw {i}",
            article_type=ArticleType.standard, target_audience="learners",
            angle="angle", meta_description="desc",
        )
        for i in range(4)
    ]

    with patch("agents.orchestrator.run_market_research", new_callable=AsyncMock) as mock_market:
        mock_market.return_value = "## Market Brief\n- pain point"
        with patch("agents.orchestrator.run_seo_agent", new_callable=AsyncMock) as mock_seo:
            mock_seo.return_value = fake_entries
            titles = await run_weekly_batch()

    assert len(titles) == 4
    assert (tmp_data_dir / "market_brief.md").exists()
    calendar = await calendar_service.load_calendar()
    assert len(calendar) == 4


async def test_orchestrator_weekly_batch_auto_setup(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_weekly_batch
    from services import calendar_service, file_service

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "COMPETITOR_PROFILES_PATH", tmp_data_dir / "competitor_profiles.md")
    monkeypatch.setattr(file_service, "MARKET_BRIEF_PATH", tmp_data_dir / "market_brief.md")

    from models.article import ArticleType, ContentCalendarEntry
    fake_entries = [
        ContentCalendarEntry(
            id=f"a-{i}", title=f"A {i}", primary_keyword=f"kw {i}",
            article_type=ArticleType.standard, target_audience="learners",
            angle="angle", meta_description="desc",
        )
        for i in range(4)
    ]

    with patch("agents.orchestrator.run_setup_research", new_callable=AsyncMock) as mock_setup:
        mock_setup.return_value = ("- fact", "**Competitor**")
        with patch("agents.orchestrator.run_market_research", new_callable=AsyncMock) as mock_market:
            mock_market.return_value = "## Market Brief"
            with patch("agents.orchestrator.run_seo_agent", new_callable=AsyncMock) as mock_seo:
                mock_seo.return_value = fake_entries
                titles = await run_weekly_batch()

    mock_setup.assert_called_once()
    assert len(titles) == 4


async def test_orchestrator_article_mode_clean(tmp_data_dir, sample_calendar_entry, sample_product_facts, monkeypatch):
    from agents.orchestrator import run_article
    from services import calendar_service, file_service
    from output_schemas import ArticleOutput, FactCheckOutput

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "DRAFTS_DIR", tmp_data_dir / "drafts")

    await file_service.write_text(tmp_data_dir / "product_facts.md", sample_product_facts)
    await calendar_service.add_entries([sample_calendar_entry])

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# Feynman Technique\n\nLearn anything.",
    )
    fake_fact_check = FactCheckOutput(passed=True, items=[])

    with patch("agents.orchestrator.run_writing_agent", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = (tmp_data_dir / "drafts" / "draft.md", fake_article)
        with patch("agents.orchestrator.run_fact_check_chain", new_callable=AsyncMock) as mock_fc:
            mock_fc.return_value = fake_fact_check
            status, draft_path = await run_article()

    from models.article import ArticleStatus
    assert status == ArticleStatus.ready_for_review
    calendar = await calendar_service.load_calendar()
    assert calendar[0].status == ArticleStatus.ready_for_review


async def test_orchestrator_article_mode_no_planned(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_article
    from services import calendar_service

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    status, draft_path = await run_article()
    assert status is None
    assert draft_path is None
```

**Step 10: Run to confirm failure:**
```bash
uv run pytest tests/test_agents.py -k "orchestrator" -v
```

**Step 11: Create `agents/orchestrator.py`:**

```python
from pathlib import Path
from typing import Optional

from agents.research_agent import run_setup_research, run_market_research
from agents.seo_agent import run_seo_agent
from agents.writing_agent import run_writing_agent
from chains.fact_check_chain import run_fact_check_chain
from config import settings
from models.article import ArticleStatus
from services import calendar_service, file_service


async def run_setup() -> None:
    """Extract product facts + crawl competitors. Run once, or when product/competitors change."""
    product_facts, competitor_profiles = await run_setup_research(settings.codebase_path)
    await file_service.write_text(file_service.PRODUCT_FACTS_PATH, product_facts)
    await file_service.write_text(file_service.COMPETITOR_PROFILES_PATH, competitor_profiles)


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
    new_entries = await run_seo_agent(research_context, existing_ids)
    await calendar_service.add_entries(new_entries)

    return [e.title for e in new_entries]


async def run_article() -> tuple[Optional[ArticleStatus], Optional[Path]]:
    """Write the next planned article. Returns (final_status, draft_path) or (None, None)."""
    entry = await calendar_service.next_planned()
    if entry is None:
        return None, None

    await calendar_service.update_status(entry.id, ArticleStatus.in_progress)
    product_facts = await file_service.read_text(file_service.PRODUCT_FACTS_PATH)
    draft_path, article = await run_writing_agent(entry, product_facts)
    fact_check = await run_fact_check_chain(product_facts, article.markdown_content)

    if fact_check.passed:
        final_status = ArticleStatus.ready_for_review
    else:
        final_status = ArticleStatus.needs_review_flagged
        flag_lines = ["\n\n---\n\n## FACT-CHECK FLAGS\n"]
        for item in fact_check.items:
            flag_lines.append(f"- **{item.verdict}**: {item.source_sentence}")
        existing_content = await file_service.read_text(draft_path)
        await file_service.write_text(draft_path, existing_content + "\n".join(flag_lines))

    await calendar_service.update_status(entry.id, final_status, draft_path=str(draft_path))
    return final_status, draft_path
```

**Step 12: Update `tests/test_agents.py` — patch the existing research agent test to use the new function name:**

Replace `run_research_agent` with `run_setup_research` in the existing test.

**Step 13: Run all agent tests — verify they pass:**
```bash
uv run pytest tests/test_agents.py -v
```

**Step 14: Commit:**
```bash
git add agents/ services/file_service.py output_schemas.py prompts/ tests/test_agents.py
git commit -m "feat: split research agent into setup + market, three orchestrator modes, prompts kick-off constants"
```

---

## Task 13: CLI Entry Point

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Rewrite `main.py`:**

```python
import argparse
import asyncio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft and Arc marketing agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py --mode setup      First-time setup: extract product facts + crawl competitors
  uv run python main.py --mode weekly     Refresh market data + plan 4 articles
  uv run python main.py --mode article    Write the next planned article
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["setup", "weekly", "article"],
        required=True,
        help="setup: product facts + competitors | weekly: market refresh + SEO | article: write draft",
    )
    return parser


async def _run_setup() -> None:
    from agents.orchestrator import run_setup
    print("Running setup: extracting product facts and crawling competitors...")
    await run_setup()
    print("Done. product_facts.md and competitor_profiles.md written to data/")
    print("Run --mode weekly next to plan articles.")


async def _run_weekly() -> None:
    from agents.orchestrator import run_weekly_batch
    print("Running weekly batch: market research → SEO → content calendar...")
    titles = await run_weekly_batch()
    print(f"\n{len(titles)} articles planned:")
    for i, title in enumerate(titles, 1):
        print(f"  {i}. {title}")
    print("\nRun --mode article to write each draft.")


async def _run_article() -> None:
    from agents.orchestrator import run_article
    from models.article import ArticleStatus
    print("Writing next planned article...")
    status, draft_path = await run_article()
    if status is None:
        print("No planned articles in the content calendar.")
        print("Run --mode weekly first to populate the calendar.")
        return
    if status == ArticleStatus.ready_for_review:
        print(f"\nDraft ready for review: {draft_path}")
        print("Review, then publish to your blog and import to Medium with canonical URL.")
    else:
        print(f"\nDraft has flagged claims — review before publishing: {draft_path}")
        print("Fact-check flags appended to the end of the draft file.")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mode == "setup":
        asyncio.run(_run_setup())
    elif args.mode == "weekly":
        asyncio.run(_run_weekly())
    elif args.mode == "article":
        asyncio.run(_run_article())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help works:**
```bash
uv run python main.py --help
```
Expected: shows `{setup,weekly,article}` as choices.

- [ ] **Step 3: Run full test suite:**
```bash
uv run pytest -v
```

- [ ] **Step 4: Commit:**
```bash
git add main.py
git commit -m "feat: CLI — add --mode setup alongside weekly and article"
```

---

## Task 14: Final Wiring Check

This task verifies the whole system can be imported without errors and all modules are wired together correctly. No real API calls — just import verification and a dry-run CLI check.

- [ ] **Step 1: Verify all modules import cleanly**

```bash
uv run python -c "
import os
os.environ.setdefault('OPENAI_API_KEY', 'sk-test')
os.environ.setdefault('TAVILY_API_KEY', 'tvly-test')
os.environ.setdefault('SERPAPI_API_KEY', 'serp-test')
os.environ.setdefault('CODEBASE_PATH', '/tmp/fake')

from agents.orchestrator import run_weekly_batch, run_article
from agents.research_agent import run_research_agent
from agents.seo_agent import run_seo_agent
from agents.writing_agent import run_writing_agent
from chains.writing_chain import run_writing_chain
from chains.fact_check_chain import run_fact_check_chain
from services.calendar_service import load_calendar, add_entries, next_planned, update_status
from services.file_service import read_text, write_text
from tools import jina_reader, google_trends, people_also_ask, list_codebase_files, read_codebase_file, tavily_search_tool
print('All modules imported successfully.')
"
```

Expected: `All modules imported successfully.`

- [ ] **Step 2: Run the complete test suite**

```bash
uv run pytest -v --tb=short
```

Expected: all tests pass, 0 failures.

- [ ] **Step 3: Verify data directory is set up correctly**

```bash
ls data/ && ls data/drafts/
```

Expected: `data/` contains `.gitkeep`, `data/drafts/` contains `.gitkeep`.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: marketing agents system complete — research, SEO, writing, orchestrator, CLI"
```

---

## Publishing Checklist (Manual Steps — Not Automated)

After running `--mode article` and reviewing a draft:

1. **Publish on your blog first** (blog is the source of truth for Google)
2. Copy the live blog post URL
3. Go to `medium.com` → New Story → **Import a Story**
4. Paste the blog URL — Medium imports the content
5. Before publishing: scroll to the editor bottom → **Advanced Settings** → set **Canonical URL** to the blog URL
6. Publish on Medium

This ensures Google credits your blog, not Medium, as the original source.
