from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from output_schemas import ResearchSetupOutput, MarketBriefOutput
from prompts.loader import load_prompt, load_system_prompt
from services.llm import get_llm

RESEARCH_SETUP_SYSTEM_PROMPT  = load_system_prompt("agents/research_setup_system.md")
RESEARCH_SETUP_KICKOFF        = "Read the codebase at {codebase_path} and crawl all competitor pages. Extract product facts from the code and build profiles for all competitors."
RESEARCH_MARKET_SYSTEM_PROMPT = load_system_prompt("agents/research_market_system.md")
RESEARCH_MARKET_KICKOFF       = "Search for current user pain points with learning tools and identify content opportunities in the personalized learning market. Use the competitor context provided."
research_setup_synthesis_prompt  = load_prompt("chains/research_setup_synthesis.md")
research_market_synthesis_prompt = load_prompt("chains/research_market_synthesis.md")
from tools import jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file


def _format_product_facts(output: ResearchSetupOutput) -> str:
    lines = ["## Draft and Arc — Product Facts\n"]
    for fact in output.product_facts:
        lines.append(f"- {fact.fact}  *(source: {fact.source_file})*")
    return "\n".join(lines)


def _format_competitor_profiles(output: ResearchSetupOutput) -> str:
    sections = ["## Competitor Profiles\n"]
    for c in output.competitors:
        sections.append(f"**{c.name}** ({c.url})")
        sections.append(f"- Positioning: {c.positioning}")
        sections.append(f"- Target audience: {c.target_audience}")
        sections.append(f"- Content gaps: {', '.join(c.content_gaps)}\n")
    return "\n".join(sections)


def _format_market_brief(output: MarketBriefOutput) -> str:
    sections = ["## Market Brief\n", "### Pain Points\n"]
    for pain in output.pain_points:
        sections.append(f"- {pain}")
    sections.append("\n### Content Opportunities\n")
    for opp in output.content_opportunities:
        sections.append(f"**{opp.angle}**")
        sections.append(f"- Why: {opp.rationale}")
        sections.append(f"- Audience: {opp.target_audience}\n")
    return "\n".join(sections)


async def run_setup_research(codebase_path: str) -> tuple[str, str]:
    """Extract product facts + build competitor profiles. Returns (product_facts_md, competitor_profiles_md)."""
    tools = [jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=RESEARCH_SETUP_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=RESEARCH_SETUP_KICKOFF.format(codebase_path=codebase_path))]
    })
    gathered_data = result["messages"][-1].content

    chain = research_setup_synthesis_prompt | get_llm().with_structured_output(ResearchSetupOutput, method="function_calling")
    output: ResearchSetupOutput = await chain.ainvoke({
        "codebase_path": codebase_path,
        "gathered_data": gathered_data,
    })

    return _format_product_facts(output), _format_competitor_profiles(output)


async def run_market_research(competitor_profiles: str) -> str:
    """Search for current pain points and content opportunities. Returns market_brief_md."""
    tools = [tavily_search_tool]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=RESEARCH_MARKET_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=RESEARCH_MARKET_KICKOFF)]
    })
    gathered_data = result["messages"][-1].content

    chain = research_market_synthesis_prompt | get_llm().with_structured_output(MarketBriefOutput, method="function_calling")
    output: MarketBriefOutput = await chain.ainvoke({
        "competitor_profiles": competitor_profiles,
        "gathered_data": gathered_data,
    })

    return _format_market_brief(output)
