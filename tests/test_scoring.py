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
