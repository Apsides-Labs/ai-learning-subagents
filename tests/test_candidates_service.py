from output_schemas import CandidateOutput
from services.candidates_service import (
    ScoredCandidate,
    parse_selected,
    render_candidates_md,
)


def _cand(title, kw, **kw_over):
    return CandidateOutput(
        title=title,
        segment=kw_over.get("segment", "devs building their first agent"),
        angle=kw_over.get("angle", "a distinct take"),
        primary_keyword=kw,
        article_type=kw_over.get("article_type", "standard"),
        blog_category=kw_over.get("blog_category", "AI Engineering"),
    )


def test_render_includes_unchecked_boxes_and_metrics():
    scored = [
        ScoredCandidate(_cand("Your first agent", "build an ai agent"), 880, 19),
        ScoredCandidate(_cand("async clicks", "python async tutorial"), None, None),
    ]
    md = render_candidates_md(scored)
    assert "### 1. Your first agent" in md
    assert "- [ ] write this" in md
    assert "volume 880 · difficulty 19" in md
    assert "volume n/a · difficulty n/a" in md   # None renders as n/a


def test_render_includes_rich_seo_fields():
    sc = ScoredCandidate(
        _cand("Your first agent", "build an ai agent"),
        880, 19,
        secondary_keywords=["ai agent python", "agent loop example"],
        serp_verdict="reachable — top results are blogs / smaller sites",
        serp_top=["devblog.com — Building agents", "example.com — Agent guide"],
        paa=["What is an agent loop?", "How do agents use tools?"],
    )
    md = render_candidates_md([sc])
    assert "Secondary keywords: ai agent python, agent loop example" in md
    assert "SERP: reachable" in md
    assert "devblog.com — Building agents" in md
    assert "People also ask: What is an agent loop?" in md


def test_parse_selected_returns_only_checked():
    scored = [
        ScoredCandidate(_cand("Keep me", "build an ai agent"), 880, 19),
        ScoredCandidate(_cand("Drop me", "python async tutorial"), 100, 5),
    ]
    md = render_candidates_md(scored)
    # Tick only the first candidate.
    md = md.replace("### 1. Keep me\n- [ ]", "### 1. Keep me\n- [x]")

    selected = parse_selected(md)
    assert len(selected) == 1
    s = selected[0]
    assert s.title == "Keep me"
    assert s.primary_keyword == "build an ai agent"   # parenthetical metrics stripped
    assert s.article_type == "standard"
    assert s.blog_category == "AI Engineering"


def test_parse_selected_handles_capital_X():
    scored = [ScoredCandidate(_cand("Pick", "build an ai agent"), 880, 19)]
    md = render_candidates_md(scored).replace("- [ ] write this", "- [X] write this")
    assert len(parse_selected(md)) == 1


def test_parse_selected_empty_when_nothing_ticked():
    scored = [ScoredCandidate(_cand("A", "kw a"), 1, 1), ScoredCandidate(_cand("B", "kw b"), 2, 2)]
    assert parse_selected(render_candidates_md(scored)) == []


def test_roundtrip_preserves_all_fields():
    c = _cand(
        "How to give an agent memory",
        "agent memory without vector database",
        segment="devs who assume they need RAG on day one",
        angle="start simpler than you think",
        article_type="topic_teaser",
        blog_category="AI Engineering",
    )
    md = render_candidates_md([ScoredCandidate(c, 320, 12)]).replace("- [ ]", "- [x]")
    out = parse_selected(md)[0]
    assert out.title == c.title
    assert out.segment == c.segment
    assert out.angle == c.angle
    assert out.primary_keyword == c.primary_keyword
    assert out.article_type == c.article_type
    assert out.blog_category == c.blog_category
