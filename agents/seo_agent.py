from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

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
    "provided. Avoid these existing topics: {existing_ids}. Use DataForSEO to "
    "validate each idea."
)
seo_synthesis_prompt = load_prompt("chains/seo_synthesis.md")


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


async def run_seo_agent(research_brief: str, existing_ids: set[str]) -> list[ContentCalendarEntry]:
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
            "messages": [HumanMessage(content=f"{research_brief}\n\n{SEO_KICKOFF.format(existing_ids=existing_ids or 'none')}")]
        })
        gathered_data = result["messages"][-1].content
    except DataForSEOBudgetExceeded as exc:
        gathered_data = (
            f"budget cap reached during tool calls — synthesis ran on partial data. "
            f"Reason: {exc}"
        )
        budget_note = "Budget exceeded mid-batch"

    chain = seo_synthesis_prompt | get_llm().with_structured_output(SEOOutput, method="function_calling")
    output: SEOOutput = await chain.ainvoke({
        "research_brief": research_brief,
        "existing_ids": ", ".join(existing_ids) if existing_ids else "none",
        "gathered_data": gathered_data,
    })

    if budget_note and not output.seo_coverage_note:
        # Belt-and-suspenders: ensure the note is set even if the LLM forgot.
        output.seo_coverage_note = budget_note

    return [_to_calendar_entry(plan) for plan in output.articles]
