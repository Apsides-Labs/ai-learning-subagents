from output_schemas import FactCheckOutput
from prompts.fact_check import fact_check_prompt
from services.llm import get_llm


async def run_fact_check_chain(product_facts: str, draft_content: str) -> FactCheckOutput:
    chain = fact_check_prompt | get_llm().with_structured_output(FactCheckOutput, method="function_calling")
    result: FactCheckOutput = await chain.ainvoke({
        "product_facts": product_facts,
        "draft_content": draft_content,
    })
    return result
