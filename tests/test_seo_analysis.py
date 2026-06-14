from services.seo_analysis import (
    is_commercial,
    is_strong_domain,
    pick_keywords,
    score_keyword,
    serp_reachability,
)


def test_commercial_terms_detected():
    assert is_commercial("best ai agent framework")
    assert is_commercial("langchain vs llamaindex")
    assert is_commercial("claude code pricing")
    assert not is_commercial("how to build an ai agent")


def test_strong_domain_detection():
    assert is_strong_domain("stackoverflow.com")
    assert is_strong_domain("www.wikipedia.org")
    assert is_strong_domain("mit.edu")
    assert is_strong_domain("whitehouse.gov")
    assert not is_strong_domain("somedevblog.com")
    assert not is_strong_domain("dev.to")


def test_score_prefers_reachable_high_volume():
    reachable = {"keyword": "build an ai agent", "search_volume": 500, "keyword_difficulty": 20}
    hard = {"keyword": "ai agent", "search_volume": 500, "keyword_difficulty": 80}
    assert score_keyword(reachable) > score_keyword(hard)


def test_score_rejects_commercial():
    assert score_keyword({"keyword": "best agent framework", "search_volume": 9999, "keyword_difficulty": 5}) == float("-inf")


def test_pick_keywords_chooses_best_and_secondary():
    ideas = [
        {"keyword": "ai agent", "search_volume": 1000, "keyword_difficulty": 75},          # hard
        {"keyword": "build an ai agent", "search_volume": 400, "keyword_difficulty": 18},   # reachable, best
        {"keyword": "ai agent python", "search_volume": 200, "keyword_difficulty": 22},
        {"keyword": "best ai agent", "search_volume": 5000, "keyword_difficulty": 10},       # commercial, excluded
    ]
    primary, secondary = pick_keywords(ideas, "fallback kw")
    assert primary["keyword"] == "build an ai agent"
    assert "best ai agent" not in secondary
    assert "ai agent python" in secondary


def test_pick_keywords_falls_back_when_no_ideas():
    primary, secondary = pick_keywords([], "my fallback")
    assert primary == {"keyword": "my fallback", "search_volume": None, "keyword_difficulty": None}
    assert secondary == []


def test_pick_keywords_falls_back_when_all_commercial():
    ideas = [{"keyword": "best x", "search_volume": 100, "keyword_difficulty": 5}]
    primary, _ = pick_keywords(ideas, "fallback")
    assert primary["keyword"] == "fallback"


def test_serp_reachability_hard():
    organic = [
        {"rank": 1, "domain": "wikipedia.org", "title": "Agent"},
        {"rank": 2, "domain": "stackoverflow.com", "title": "Q"},
        {"rank": 3, "domain": "geeksforgeeks.org", "title": "G"},
        {"rank": 4, "domain": "someblog.com", "title": "B"},
        {"rank": 5, "domain": "another.com", "title": "A"},
    ]
    verdict, top = serp_reachability(organic)
    assert verdict.startswith("hard")
    assert len(top) == 3


def test_serp_reachability_reachable():
    organic = [
        {"rank": 1, "domain": "someblog.com", "title": "B"},
        {"rank": 2, "domain": "dev.to", "title": "D"},
    ]
    verdict, _ = serp_reachability(organic)
    assert verdict.startswith("reachable")


def test_serp_reachability_empty():
    verdict, top = serp_reachability([])
    assert verdict == "no SERP data"
    assert top == []
