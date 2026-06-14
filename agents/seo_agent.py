import httpx
from langchain.agents import create_agent
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from models.article import ArticleType, ContentCalendarEntry
from output_schemas import SEOOutput
from prompts.loader import load_prompt, load_system_prompt
from services.dataforseo_client import DataForSEOBudgetExceeded
from services.llm import get_llm
from tools.dataforseo import (
    dfs_serp_live_advanced,
    dfs_keyword_suggestions,
    dfs_bulk_keyword_data,
)


SEO_AGENT_SYSTEM_PROMPT = load_system_prompt("agents/seo_system.md")
SEO_KICKOFF = (
    "Research keywords and SERP data for 4 article ideas based on the context "
    "provided. Avoid ALL topics already covered (listed below). Use DataForSEO to "
    "validate each idea.\n\nALREADY COVERED — do not overlap any of these topics, "
    "keywords, or closely related subtopics:\n{existing_coverage}"
)
seo_synthesis_prompt = load_prompt("chains/seo_synthesis.md")


async def _synthesize_with_retry(chain, payload: dict, attempts: int = 3) -> SEOOutput:
    """Run the structured-output synthesis, re-sampling on malformed output.

    The LLM occasionally emits invalid JSON in its tool call (e.g. a stray
    delimiter between article objects), which the strict SEOOutput schema
    rejects with a ValidationError. Re-sampling almost always fixes a transient
    malformation, so retry a few times before surfacing the failure — otherwise
    one bad generation crashes the whole weekly batch.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await chain.ainvoke(payload)
        except (ValidationError, OutputParserException) as exc:
            last_exc = exc
            print(f"  SEO synthesis returned invalid output (attempt {attempt}/{attempts}); re-sampling...")
    raise RuntimeError(
        f"SEO synthesis failed to produce valid output after {attempts} attempts"
    ) from last_exc


def _to_calendar_entry(plan) -> ContentCalendarEntry:
    return ContentCalendarEntry(
        id=plan.id,
        title=plan.title,
        primary_keyword=plan.primary_keyword,
        secondary_keywords=plan.secondary_keywords,
        search_intent=plan.search_intent,
        article_type=ArticleType(plan.article_type),
        target_audience=plan.target_audience,
        angle=plan.angle,
        meta_description=plan.meta_description,
        suggested_headings=plan.suggested_headings,
        cta_prompt=plan.cta_prompt,
        blog_category=plan.blog_category,
        serp_context=plan.serp_context,
    )


async def run_seo_agent(research_brief: str, existing_ids: set[str], existing_coverage: str = "") -> list[ContentCalendarEntry]:
    """Run the SEO agent. Returns up to 4 new ContentCalendarEntry items.

    If DataForSEOBudgetExceeded fires mid-batch, falls through to synthesis with
    whatever partial data the agent gathered and prompts the synthesis LLM to
    populate seo_coverage_note. Does not crash on budget exhaustion.
    """
    tools = [
        dfs_serp_live_advanced,
        dfs_keyword_suggestions,
        dfs_bulk_keyword_data,
    ]
    agent = create_agent(get_llm(), tools=tools, system_prompt=SEO_AGENT_SYSTEM_PROMPT)

    budget_note = ""
    try:
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=f"{research_brief}\n\n{SEO_KICKOFF.format(existing_coverage=existing_coverage or 'none')}")]
        })
        gathered_data = result["messages"][-1].content
    except DataForSEOBudgetExceeded as exc:
        gathered_data = (
            f"budget cap reached during tool calls — synthesis ran on partial data. "
            f"Reason: {exc}"
        )
        budget_note = "Budget exceeded mid-batch"
    except httpx.HTTPError as exc:
        # A DataForSEO request failed terminally even after the client's
        # retries (e.g. the API is down or persistently timing out). Fall
        # through to synthesis on whatever the agent gathered rather than
        # crashing the whole weekly batch.
        gathered_data = (
            f"DataForSEO request failed during tool calls — synthesis ran on "
            f"partial data. Reason: {type(exc).__name__}: {exc}"
        )
        budget_note = "DataForSEO request failed mid-batch"

    chain = seo_synthesis_prompt | get_llm().with_structured_output(SEOOutput, method="function_calling")
    output: SEOOutput = await _synthesize_with_retry(chain, {
        "research_brief": research_brief,
        "existing_coverage": existing_coverage or "none",
        "gathered_data": gathered_data,
    })

    if budget_note and not output.seo_coverage_note:
        # Belt-and-suspenders: ensure the note is set even if the LLM forgot.
        output.seo_coverage_note = budget_note

    return [_to_calendar_entry(plan) for plan in output.articles]
