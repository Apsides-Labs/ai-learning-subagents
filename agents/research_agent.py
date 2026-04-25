from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from output_schemas import ResearchOutput
from prompts.research import RESEARCH_AGENT_SYSTEM_PROMPT, research_synthesis_prompt
from services.llm import get_llm
from tools import jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file


def _format_product_facts(output: ResearchOutput) -> str:
    lines = ["## Draft and Arc — Product Facts\n"]
    for fact in output.product_facts:
        lines.append(f"- {fact.fact}  *(source: {fact.source_file})*")
    return "\n".join(lines)


def _format_research_brief(output: ResearchOutput) -> str:
    sections = ["## Draft and Arc — Research Brief\n"]

    sections.append("### Competitor Analysis\n")
    for c in output.competitors:
        sections.append(f"**{c.name}** ({c.url})")
        sections.append(f"- Positioning: {c.positioning}")
        sections.append(f"- Target audience: {c.target_audience}")
        sections.append(f"- Content gaps: {', '.join(c.content_gaps)}\n")

    sections.append("### Market Pain Points\n")
    for pain in output.pain_points:
        sections.append(f"- {pain}")

    sections.append("\n### Content Opportunities\n")
    for opp in output.content_opportunities:
        sections.append(f"**{opp.angle}**")
        sections.append(f"- Why: {opp.rationale}")
        sections.append(f"- Audience: {opp.target_audience}\n")

    return "\n".join(sections)


async def run_research_agent(codebase_path: str) -> tuple[str, str]:
    """Run the research agent. Returns (product_facts_md, research_brief_md)."""
    tools = [jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file]
    agent = create_react_agent(get_llm(), tools=tools, state_modifier=RESEARCH_AGENT_SYSTEM_PROMPT)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=f"Research the product codebase at {codebase_path} and all competitors. Gather all data now.")]
    })
    gathered_data = result["messages"][-1].content

    chain = research_synthesis_prompt | get_llm().with_structured_output(ResearchOutput, method="function_calling")
    output: ResearchOutput = await chain.ainvoke({
        "codebase_path": codebase_path,
        "gathered_data": gathered_data,
    })

    return _format_product_facts(output), _format_research_brief(output)
