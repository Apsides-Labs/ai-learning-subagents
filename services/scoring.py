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
