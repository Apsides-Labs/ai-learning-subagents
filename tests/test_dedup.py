from models.article import ArticleType, ContentCalendarEntry
from services.dedup import covered_tools, filter_duplicates


def _entry(id, title, primary, secondary=None):
    return ContentCalendarEntry(
        id=id,
        title=title,
        primary_keyword=primary,
        secondary_keywords=secondary or [],
        article_type=ArticleType.standard,
        target_audience="self-learners",
        angle="angle",
        meta_description="meta",
        cta_prompt="cta",
    )


EXISTING = [
    _entry("anki-1", "Why people quit Anki at week 3", "anki review queue too long"),
    _entry(
        "self-study",
        "How to build a self-study roadmap",
        "how do i create a self-study plan",
        ["self-learning roadmap", "study plan without teacher"],
    ),
]


def test_rejects_repeat_tool():
    cand = [_entry("1", "Anki feels like memorization not learning", "anki feels like memorization")]
    kept, rejected = filter_duplicates(EXISTING, cand)
    assert kept == []
    assert len(rejected) == 1
    assert "anki" in rejected[0][1]


def test_rejects_duplicate_primary_keyword():
    cand = [_entry("4", "First 30-day self-learning roadmap", "how do i create a self-study plan")]
    kept, rejected = filter_duplicates(EXISTING, cand)
    assert kept == []
    assert "duplicate primary keyword" in rejected[0][1]


def test_rejects_keyword_matching_existing_secondary():
    cand = [_entry("x", "A study plan without a teacher", "study plan without teacher")]
    kept, rejected = filter_duplicates(EXISTING, cand)
    assert kept == []


def test_keeps_fresh_topic():
    cand = [_entry("2", "Why Notion feels slow for note-taking", "notion too slow note taking")]
    kept, rejected = filter_duplicates(EXISTING, cand)
    assert len(kept) == 1
    assert rejected == []


def test_intra_batch_dedup_on_fresh_tool():
    cand = [
        _entry("a", "Notion is too slow", "notion slow note taking"),
        _entry("b", "Make Notion faster", "speed up notion"),
    ]
    kept, rejected = filter_duplicates(EXISTING, cand)
    assert len(kept) == 1
    assert kept[0].id == "a"
    assert "notion" in rejected[0][1]


def test_covered_tools_reports_saturated_tools():
    assert covered_tools(EXISTING) == {"anki"}


def test_covered_tools_empty_when_no_tools():
    entries = [_entry("x", "How to build a study routine", "study routine that sticks")]
    assert covered_tools(entries) == set()


def test_tool_matched_on_word_boundary_not_substring():
    # "roam" must not match inside "roaming"; ensure no false positive.
    cand = [_entry("c", "Learning while roaming abroad", "study while traveling")]
    kept, _ = filter_duplicates(EXISTING, cand)
    assert len(kept) == 1
