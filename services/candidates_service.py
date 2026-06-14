"""Read/write the human-in-the-loop article candidate shortlist (candidates.md).

`propose` mode writes candidates with SEO numbers and an unchecked box per idea.
The human ticks `[x]` the ones to write. `produce` mode parses the ticked ones
and runs deep SEO + drafting on just those.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from output_schemas import CandidateOutput
from services.file_service import atomic_write_text, read_text

CANDIDATES_PATH = Path("data/candidates.md")

_HEADER = """# Article candidates

Tick `[x]` the ones you want written (change `[ ]` to `[x]`), tweak titles/angles
inline if you like, then run `--mode produce` on the ticked ones.

SEO numbers come from DataForSEO (US, English). `n/a` = no data returned for that keyword.
"""


@dataclass
class ScoredCandidate:
    candidate: CandidateOutput
    search_volume: int | None
    keyword_difficulty: int | None
    secondary_keywords: list[str] = field(default_factory=list)
    serp_verdict: str = ""
    serp_top: list[str] = field(default_factory=list)
    paa: list[str] = field(default_factory=list)


def _fmt(value: int | None) -> str:
    return str(value) if value is not None else "n/a"


def render_candidates_md(scored: list[ScoredCandidate]) -> str:
    blocks = [_HEADER]
    for i, sc in enumerate(scored, 1):
        c = sc.candidate
        lines = [
            f"---\n",
            f"### {i}. {c.title}",
            "- [ ] write this",
            f"- Segment: {c.segment}",
            f"- Angle: {c.angle}",
            f"- Primary keyword: {c.primary_keyword}  (volume {_fmt(sc.search_volume)} · difficulty {_fmt(sc.keyword_difficulty)})",
        ]
        if sc.secondary_keywords:
            lines.append(f"- Secondary keywords: {', '.join(sc.secondary_keywords)}")
        if sc.serp_verdict:
            lines.append(f"- SERP: {sc.serp_verdict}")
        for top in sc.serp_top:
            lines.append(f"    - {top}")
        if sc.paa:
            lines.append(f"- People also ask: {' | '.join(sc.paa[:4])}")
        lines.append(f"- Type: {c.article_type} · Category: {c.blog_category}")
        blocks.append("\n".join(lines) + "\n")
    return "\n".join(blocks)


async def write_candidates(scored: list[ScoredCandidate]) -> Path:
    await atomic_write_text(CANDIDATES_PATH, render_candidates_md(scored))
    return CANDIDATES_PATH


# --- parsing (used by produce mode) ---

_FIELD_RE = {
    "segment": re.compile(r"^-\s*Segment:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
    "angle": re.compile(r"^-\s*Angle:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
    "primary_keyword": re.compile(r"^-\s*Primary keyword:\s*(.+?)\s*(?:\(|$)", re.MULTILINE | re.IGNORECASE),
}
_TYPE_CAT_RE = re.compile(r"^-\s*Type:\s*(\S+)\s*·\s*Category:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_CHECKED_RE = re.compile(r"^-\s*\[[xX]\]\s*write this", re.MULTILINE)
_TITLE_RE = re.compile(r"^###\s*\d+\.\s*(.+)$", re.MULTILINE)


def _parse_block(block: str) -> CandidateOutput | None:
    title_m = _TITLE_RE.search(block)
    if not title_m:
        return None
    segment = _FIELD_RE["segment"].search(block)
    angle = _FIELD_RE["angle"].search(block)
    pk = _FIELD_RE["primary_keyword"].search(block)
    type_cat = _TYPE_CAT_RE.search(block)
    return CandidateOutput(
        title=title_m.group(1).strip(),
        segment=segment.group(1).strip() if segment else "",
        angle=angle.group(1).strip() if angle else "",
        primary_keyword=pk.group(1).strip() if pk else "",
        article_type=(type_cat.group(1).strip() if type_cat else "standard"),
        blog_category=(type_cat.group(2).strip() if type_cat else ""),
    )


def parse_selected(md_text: str) -> list[CandidateOutput]:
    """Return the candidates the human ticked `[x]`, in file order."""
    selected: list[CandidateOutput] = []
    # Split on the per-candidate heading; keep only blocks with a checked box.
    blocks = re.split(r"(?=^###\s)", md_text, flags=re.MULTILINE)
    for block in blocks:
        if _CHECKED_RE.search(block):
            parsed = _parse_block(block)
            if parsed is not None:
                selected.append(parsed)
    return selected


async def load_selected() -> list[CandidateOutput]:
    if not CANDIDATES_PATH.exists():
        return []
    return parse_selected(await read_text(CANDIDATES_PATH))
