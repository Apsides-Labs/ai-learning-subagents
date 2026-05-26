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
