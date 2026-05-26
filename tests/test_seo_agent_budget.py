"""SEO agent's behaviour when DataForSEOBudgetExceeded fires mid-batch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_run_seo_agent_falls_through_on_budget_exceeded():
    """When the @tool raises DataForSEOBudgetExceeded, the agent should NOT crash.
    Instead it should run synthesis on the partial data and set seo_coverage_note."""
    from agents import seo_agent
    from services.dataforseo_client import DataForSEOBudgetExceeded
    from output_schemas import SEOOutput, ArticlePlanOutput

    fake_messages_result = {
        "messages": [
            MagicMock(content="some partial gathered data before the cap fired")
        ]
    }

    # The agent ainvoke raises midway.
    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(
        side_effect=DataForSEOBudgetExceeded("cost cap")
    )

    fake_output = SEOOutput(
        articles=[],
        seo_coverage_note="Budget cap reached; synthesis ran on partial data."
    )
    fake_chain = MagicMock()
    fake_chain.ainvoke = AsyncMock(return_value=fake_output)

    with patch.object(seo_agent, "create_agent", return_value=fake_agent), \
         patch.object(seo_agent, "get_llm") as mock_get_llm, \
         patch.object(seo_agent, "seo_synthesis_prompt") as mock_prompt:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_get_llm.return_value = mock_llm
        # The agent code does `seo_synthesis_prompt | get_llm()...` then `.ainvoke(...)`.
        # Force `prompt | llm` to return our fake chain so we can assert ainvoke was hit.
        mock_prompt.__or__ = MagicMock(return_value=fake_chain)

        result = await seo_agent.run_seo_agent("research brief", existing_ids=set())

    assert result == []  # No articles produced (consistent with empty SEOOutput).
    # The synthesis chain WAS called (i.e. we did not crash on the cap).
    fake_chain.ainvoke.assert_called_once()
