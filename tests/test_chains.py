import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from models.article import ArticleType, ContentCalendarEntry


@pytest.fixture
def entry(sample_calendar_entry) -> ContentCalendarEntry:
    return sample_calendar_entry


async def test_writing_chain_returns_article_output(entry, sample_product_facts):
    from output_schemas import ArticleOutput
    from chains.writing_chain import run_writing_chain

    mock_output = ArticleOutput(
        title=entry.title,
        primary_keyword=entry.primary_keyword,
        meta_description=entry.meta_description,
        markdown_content="# The Feynman Technique\n\nYou can learn anything...",
        article_summary="A guide to using the Feynman Technique to learn programming concepts faster.",
        key_takeaway="Explaining a concept in simple terms reveals what you actually understand.",
    )

    with patch("chains.writing_chain.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        with patch("chains.writing_chain.writing_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = await run_writing_chain(entry, sample_product_facts)

    assert result.title == entry.title
    assert "Feynman" in result.markdown_content


async def test_fact_check_chain_passes_clean_draft(sample_product_facts):
    from output_schemas import FactCheckOutput
    from chains.fact_check_chain import run_fact_check_chain

    mock_output = FactCheckOutput(passed=True, items=[])
    clean_draft = "The Feynman Technique is a study method. Try it today."

    with patch("chains.fact_check_chain.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        with patch("chains.fact_check_chain.fact_check_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = await run_fact_check_chain(sample_product_facts, clean_draft)

    assert result.passed is True
    assert result.items == []


async def test_fact_check_chain_flags_unsupported_claim(sample_product_facts):
    from output_schemas import FactCheckOutput, FactCheckItemOutput
    from chains.fact_check_chain import run_fact_check_chain

    mock_output = FactCheckOutput(
        passed=False,
        items=[
            FactCheckItemOutput(
                claim="Draft and Arc offers video lessons",
                verdict="UNSUPPORTED",
                source_sentence="Draft and Arc offers video lessons for visual learners.",
            )
        ],
    )
    bad_draft = "Draft and Arc offers video lessons for visual learners."

    with patch("chains.fact_check_chain.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        with patch("chains.fact_check_chain.fact_check_prompt") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = await run_fact_check_chain(sample_product_facts, bad_draft)

    assert result.passed is False
    assert result.items[0].verdict == "UNSUPPORTED"
