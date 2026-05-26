"""Deterministic measurement dataclasses + URL normalization + LLM-input helper.

Schema split (see spec Section 6): anything with a number lives here as a
plain dataclass and is never produced by an LLM. The LLM-produced fields
(actions, verdicts, coverage_note) live in output_schemas.py as Pydantic
models. The merged FinalMeasurementReport (defined here too) is what both
renderers consume.
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
