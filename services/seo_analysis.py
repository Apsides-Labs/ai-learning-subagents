"""Pure functions for turning raw DataForSEO data into a pick decision.

Kept separate from the client (which only fetches) and the agent (which only
orchestrates) so the selection heuristics are unit-testable in isolation —
same split as services/scoring.py for the measurement side.
"""

# Commercial / non-informational modifiers. A keyword containing one of these is
# the wrong intent for an educational article, so it's deprioritised hard.
COMMERCIAL_TERMS = frozenset({
    "best", "vs", "review", "reviews", "alternative", "alternatives",
    "pricing", "price", "cheap", "buy", "discount", "coupon", "download",
    "free download", "tutorial pdf", "course", "certification",
})

# High-authority domains that make a SERP hard to crack for a new blog. Curated
# for the developer/AI niche (docs, reference sites, big aggregators). Suffix
# checks below also catch any .gov / .edu.
STRONG_DOMAINS = frozenset({
    "wikipedia.org", "stackoverflow.com", "github.com",
    "developer.mozilla.org", "w3schools.com", "geeksforgeeks.org",
    "realpython.com", "freecodecamp.org", "datacamp.com", "programiz.com",
    "coursera.org", "edx.org", "khanacademy.org", "udemy.com",
    "python.org", "docs.python.org", "nodejs.org", "developer.android.com",
    "anthropic.com", "docs.anthropic.com", "openai.com", "platform.openai.com",
    "medium.com",
})

_STRONG_SUFFIXES = (".gov", ".edu")


def is_commercial(keyword: str) -> bool:
    words = set(keyword.lower().split())
    if words & COMMERCIAL_TERMS:
        return True
    return any(term in keyword.lower() for term in COMMERCIAL_TERMS if " " in term)


def is_strong_domain(domain: str) -> bool:
    d = (domain or "").lower().removeprefix("www.")
    if d in STRONG_DOMAINS:
        return True
    return any(d.endswith(suf) for suf in _STRONG_SUFFIXES)


def score_keyword(idea: dict) -> float:
    """Higher is better. Rewards real volume + reachable difficulty, punishes
    commercial intent and unknown/high difficulty."""
    if is_commercial(idea.get("keyword", "")):
        return float("-inf")

    volume = idea.get("search_volume") or 0
    difficulty = idea.get("keyword_difficulty")

    if difficulty is None:
        # No difficulty data — usable but discounted vs. a known-reachable one.
        return volume * 0.4
    if difficulty <= 30:
        return volume - difficulty            # reachable: volume dominates
    if difficulty <= 50:
        return volume * 0.3 - difficulty      # borderline
    return volume * 0.1 - difficulty * 2      # hard: heavily penalised


def pick_keywords(
    ideas: list[dict],
    fallback_keyword: str,
    *,
    max_secondary: int = 3,
) -> tuple[dict, list[str]]:
    """Choose the best primary keyword and a few secondary ones.

    Returns (primary, secondary_keywords). `primary` is a dict with keys
    keyword/search_volume/keyword_difficulty. Falls back to `fallback_keyword`
    (no metrics) when no usable ideas exist.
    """
    usable = [i for i in ideas if i.get("keyword") and score_keyword(i) != float("-inf")]
    if not usable:
        return (
            {"keyword": fallback_keyword, "search_volume": None, "keyword_difficulty": None},
            [],
        )

    ranked = sorted(usable, key=score_keyword, reverse=True)
    primary = ranked[0]
    secondary = [i["keyword"] for i in ranked[1 : 1 + max_secondary]]
    return primary, secondary


def serp_reachability(organic: list[dict]) -> tuple[str, list[str]]:
    """Return (verdict, top_lines) describing how crackable the SERP looks.

    `top_lines` are up to three "domain — title" strings for the human to skim.
    """
    if not organic:
        return "no SERP data", []

    top5 = organic[:5]
    strong = sum(1 for d in top5 if is_strong_domain(d.get("domain", "")))
    if strong >= 3:
        verdict = f"hard — {strong}/5 top results are high-authority domains"
    elif strong == 0:
        verdict = "reachable — top results are blogs / smaller sites"
    else:
        verdict = f"mixed — {strong}/5 top results are high-authority"

    top_lines = [
        f"{d.get('domain', '')} — {d.get('title', '')}".strip(" —")
        for d in organic[:3]
    ]
    return verdict, top_lines
