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
