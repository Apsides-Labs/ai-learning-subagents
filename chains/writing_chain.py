from output_schemas import ArticleOutput
from prompts.loader import load_prompt
from services.llm import get_llm

writing_prompt = load_prompt("chains/writing.md")
from models.article import ContentCalendarEntry


async def run_writing_chain(entry: ContentCalendarEntry, product_facts: str) -> ArticleOutput:
    chain = writing_prompt | get_llm().with_structured_output(ArticleOutput, method="function_calling")
    result: ArticleOutput = await chain.ainvoke({
        "product_facts": product_facts,
        "title": entry.title,
        "primary_keyword": entry.primary_keyword,
        "secondary_keywords": ", ".join(entry.secondary_keywords),
        "article_type": entry.article_type,
        "target_audience": entry.target_audience,
        "angle": entry.angle,
        "suggested_headings": "\n".join(entry.suggested_headings),
        "cta_prompt": entry.cta_prompt,
        "meta_description": entry.meta_description,
    })
    return result
