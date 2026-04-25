from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from models.article import ArticleType, ContentCalendarEntry
from output_schemas import SEOOutput
from prompts.loader import load_prompt, load_system_prompt

SEO_AGENT_SYSTEM_PROMPT = load_system_prompt("seo_system.md")
SEO_KICKOFF             = load_system_prompt("seo_kickoff.md")
seo_synthesis_prompt    = load_prompt("seo_synthesis.md")
from services.llm import get_llm
from tools import tavily_search_tool, people_also_ask, google_trends


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
    )


async def run_seo_agent(research_brief: str, existing_ids: set[str]) -> list[ContentCalendarEntry]:
    """Run the SEO agent. Returns 4 new ContentCalendarEntry items."""
    tools = [tavily_search_tool, people_also_ask, google_trends]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=SEO_AGENT_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=SEO_KICKOFF.format(existing_ids=existing_ids or "none"))]
    })
    gathered_data = result["messages"][-1].content

    chain = seo_synthesis_prompt | get_llm().with_structured_output(SEOOutput, method="function_calling")
    output: SEOOutput = await chain.ainvoke({
        "research_brief": research_brief,
        "existing_ids": ", ".join(existing_ids) if existing_ids else "none",
        "gathered_data": gathered_data,
    })

    return [_to_calendar_entry(plan) for plan in output.articles]
