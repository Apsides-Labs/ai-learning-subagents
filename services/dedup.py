"""Deterministic dedup guard for newly planned articles.

The SEO synthesis prompt asks the LLM not to repeat tools or topics already in
the calendar, but that is an honor-system rule the model has violated in
practice — a third Anki article, a third Duolingo article, and a near-exact
duplicate of an existing self-study-roadmap entry all slipped through. This
module enforces the ban in code so a violating candidate never reaches the
calendar, regardless of how the LLM rationalises the angle.
"""

import re

from models.article import ContentCalendarEntry

# Known tools/apps in Draft and Arc's space. Mirrors the audience scope in
# prompts/md/agents/research_market_system.md. If a tool here is the focus of
# any existing calendar entry, it is banned as the focus of a new article.
KNOWN_TOOLS: frozenset[str] = frozenset({
    "anki", "remnote", "mochi",
    "notion", "obsidian", "roam",
    "chatgpt", "claude", "perplexity",
    "coursera", "edx", "udemy", "khan academy",
    "duolingo", "babbel", "busuu",
})


def _normalize(text: str) -> str:
    """Lowercase and collapse punctuation to spaces for token matching."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def _tools_in(text: str) -> set[str]:
    """Return the known tools mentioned in `text`, matched on word boundaries."""
    padded = f" {_normalize(text)} "
    return {tool for tool in KNOWN_TOOLS if f" {tool} " in padded}


def covered_tools(entries: list[ContentCalendarEntry]) -> set[str]:
    """Return the set of known tools that are the focus of any existing entry.

    Used to tell the upstream market-research agent which tools are already
    saturated, so it stops surfacing them in the first place rather than having
    them filtered out downstream.
    """
    found: set[str] = set()
    for e in entries:
        found |= _tools_in(e.title) | _tools_in(e.primary_keyword)
    return found


def filter_duplicates(
    existing: list[ContentCalendarEntry],
    candidates: list[ContentCalendarEntry],
) -> tuple[list[ContentCalendarEntry], list[tuple[ContentCalendarEntry, str]]]:
    """Split candidates into (kept, rejected_with_reason).

    A candidate is rejected if either:
    - its primary keyword (normalized) matches any existing primary or secondary
      keyword — an exact or near-duplicate topic, or
    - a known tool appears in its title or primary keyword and that tool already
      appears in an existing entry — the hard tool ban.

    Accepted candidates also seed the banned set, so two new entries in the same
    batch cannot both claim a freshly introduced tool or keyword.
    """
    banned_tools: set[str] = set()
    seen_keywords: set[str] = set()
    for e in existing:
        banned_tools |= _tools_in(e.title) | _tools_in(e.primary_keyword)
        seen_keywords.add(_normalize(e.primary_keyword))
        seen_keywords.update(_normalize(kw) for kw in e.secondary_keywords)

    kept: list[ContentCalendarEntry] = []
    rejected: list[tuple[ContentCalendarEntry, str]] = []
    for c in candidates:
        cand_pk = _normalize(c.primary_keyword)
        clash = (_tools_in(c.title) | _tools_in(c.primary_keyword)) & banned_tools
        if cand_pk in seen_keywords:
            rejected.append((c, f"duplicate primary keyword: {c.primary_keyword!r}"))
        elif clash:
            rejected.append((c, f"tool already covered: {', '.join(sorted(clash))}"))
        else:
            kept.append(c)
            banned_tools |= _tools_in(c.title) | _tools_in(c.primary_keyword)
            seen_keywords.add(cand_pk)
            seen_keywords.update(_normalize(kw) for kw in c.secondary_keywords)

    return kept, rejected
