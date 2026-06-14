"""Propose mode: generate a diverse, segment-anchored candidate shortlist.

The LLM generates ideas from the editorial focus while avoiding existing
coverage; DataForSEO then attaches search volume + difficulty so the human's
pick is informed. No web search and no drafting happen here — this is the
cheap, fast "what should we write?" step.
"""

import httpx
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from output_schemas import CandidateBatchOutput
from prompts.loader import load_prompt
from services.candidates_service import ScoredCandidate
from services.dataforseo_client import DataForSEOBudgetExceeded, get_client
from services.llm import get_llm
from services.seo_analysis import pick_keywords, serp_reachability

propose_prompt = load_prompt("chains/propose.md")


async def _generate(editorial_focus: str, existing_coverage: str, n: int) -> CandidateBatchOutput:
    chain = propose_prompt | get_llm().with_structured_output(
        CandidateBatchOutput, method="function_calling"
    )
    payload = {
        "editorial_focus": editorial_focus,
        "existing_coverage": existing_coverage or "none",
        "n": n,
    }
    # Re-sample once on malformed structured output (see seo_agent for rationale).
    for attempt in range(2):
        try:
            return await chain.ainvoke(payload)
        except (ValidationError, OutputParserException):
            if attempt == 1:
                raise
            print("  proposer returned invalid output; re-sampling...")
    raise RuntimeError("unreachable")


async def _enrich_one(candidate) -> ScoredCandidate:
    """Replace the LLM's guessed keyword with a real searched one, then read the SERP.

    Two DataForSEO calls per candidate: keyword_suggestions (real variants with
    volume + difficulty) and a SERP snapshot (reachability + People Also Ask).
    """
    client = get_client()
    ideas = await client.keyword_ideas(candidate.primary_keyword, limit=30)
    primary, secondary = pick_keywords(ideas, candidate.primary_keyword)
    candidate.primary_keyword = primary["keyword"]  # swap guess → real keyword

    # Backfill volume/difficulty when keyword discovery didn't carry them
    # (common for niche long-tail seeds) so the human still sees real numbers.
    if primary.get("search_volume") is None and primary.get("keyword_difficulty") is None:
        metrics = await client.bulk_keyword_metrics([candidate.primary_keyword])
        m = metrics.get(candidate.primary_keyword, {})
        primary["search_volume"] = m.get("search_volume")
        primary["keyword_difficulty"] = m.get("keyword_difficulty")

    snap = await client.serp_snapshot(candidate.primary_keyword)
    verdict, top = serp_reachability(snap["organic"])

    return ScoredCandidate(
        candidate=candidate,
        search_volume=primary.get("search_volume"),
        keyword_difficulty=primary.get("keyword_difficulty"),
        secondary_keywords=secondary,
        serp_verdict=verdict,
        serp_top=top,
        paa=snap["paa"],
    )


async def _attach_seo(candidates) -> list[ScoredCandidate]:
    """Enrich each candidate with real SEO data, sequentially (the cost tracker
    is shared and not concurrency-safe). Degrades gracefully: a per-candidate
    network error drops just that candidate's data; a budget cap stops
    enrichment and emits the remainder bare."""
    scored: list[ScoredCandidate] = []
    for i, c in enumerate(candidates):
        try:
            scored.append(await _enrich_one(c))
        except DataForSEOBudgetExceeded as exc:
            print(f"  SEO budget reached after {len(scored)} enriched: {exc}")
            scored.extend(ScoredCandidate(rest, None, None) for rest in candidates[i:])
            break
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 402:
                print(
                    "  DataForSEO balance exhausted (402 Payment Required) — top up at "
                    "https://app.dataforseo.com to refresh SEO data. Writing remaining "
                    "candidates without numbers."
                )
                scored.extend(ScoredCandidate(rest, None, None) for rest in candidates[i:])
                break
            print(f"  SEO enrichment failed for {c.primary_keyword!r}: HTTP {code}")
            scored.append(ScoredCandidate(c, None, None))
        except httpx.HTTPError as exc:
            print(f"  SEO enrichment failed for {c.primary_keyword!r}: {type(exc).__name__}")
            scored.append(ScoredCandidate(c, None, None))
    return scored


async def run_propose_agent(
    editorial_focus: str,
    existing_coverage: str = "",
    n: int = 12,
) -> list[ScoredCandidate]:
    """Generate `n` candidates and attach SEO metrics. Returns scored candidates."""
    batch = await _generate(editorial_focus, existing_coverage, n)
    return await _attach_seo(batch.candidates)
