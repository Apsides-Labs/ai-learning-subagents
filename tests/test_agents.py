import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


async def test_research_agent_returns_product_facts_and_brief():
    from agents.research_agent import run_research_agent

    gathered_data = "Codebase: courses have knowledge_level, daily_minutes. Competitor Duolingo: gamified language app."
    fake_gather_result = {"messages": [AIMessage(content=gathered_data)]}

    from output_schemas import ResearchOutput, CompetitorOutput, ContentOpportunityOutput, ProductFactOutput
    fake_synthesis = ResearchOutput(
        competitors=[
            CompetitorOutput(
                name="Duolingo",
                url="https://duolingo.com",
                positioning="gamified language",
                target_audience="casual learners",
                content_gaps=["no custom topics"],
            )
        ],
        pain_points=["no personalised pacing"],
        content_opportunities=[
            ContentOpportunityOutput(
                angle="Feynman technique",
                rationale="gap in competitor content",
                target_audience="programmers",
            )
        ],
        product_facts=[
            ProductFactOutput(
                fact="Users set daily learning time (default: 20 minutes)",
                source_file="app/models/course.py",
            )
        ],
    )

    with patch("agents.research_agent.create_react_agent") as mock_create:
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_gather_result)
        mock_create.return_value = mock_agent

        with patch("agents.research_agent.get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=fake_synthesis)
            mock_llm.with_structured_output.return_value = mock_llm
            mock_llm_fn.return_value = mock_llm

            with patch("agents.research_agent.research_synthesis_prompt") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                product_facts, research_brief = await run_research_agent("/fake/codebase")

    assert "Users set daily learning time" in product_facts
    assert "Duolingo" in research_brief
    assert "Feynman technique" in research_brief


async def test_seo_agent_returns_calendar_entries():
    from agents.seo_agent import run_seo_agent
    from models.article import ArticleType

    gathered_data = "PAA: how to learn Spanish fast. Trend: rising. Competition: low."
    fake_gather_result = {"messages": [AIMessage(content=gathered_data)]}

    from output_schemas import SEOOutput, ArticlePlanOutput
    fake_synthesis = SEOOutput(articles=[
        ArticlePlanOutput(
            id="learn-spanish-30-days",
            title="How to Learn Spanish in 30 Days",
            primary_keyword="learn Spanish fast",
            secondary_keywords=["Spanish for beginners"],
            search_intent="informational",
            article_type="topic_teaser",
            target_audience="beginners",
            angle="personalized pacing beats Duolingo streaks",
            meta_description="Learn Spanish in 30 days with a personalised plan.",
            suggested_headings=["H2: Why 30 days works"],
            cta_prompt="Create a 30-day beginner Spanish course for me",
        ),
        ArticlePlanOutput(
            id="feynman-technique-study",
            title="The Feynman Technique: Learn Anything by Teaching It",
            primary_keyword="feynman technique study",
            secondary_keywords=[],
            search_intent="informational",
            article_type="standard",
            target_audience="self-directed learners",
            angle="Draft and Arc builds Feynman prompts into every lesson",
            meta_description="Master any subject with the Feynman Technique.",
            suggested_headings=["H2: What is Feynman Technique"],
            cta_prompt="",
        ),
        ArticlePlanOutput(
            id="learn-python-2-weeks",
            title="How to Learn Python in 2 Weeks",
            primary_keyword="learn python fast",
            secondary_keywords=[],
            search_intent="informational",
            article_type="topic_teaser",
            target_audience="beginners",
            angle="daily 20-minute sessions with a structured syllabus",
            meta_description="Learn Python in 2 weeks with a daily plan.",
            suggested_headings=["H2: The 2-week plan"],
            cta_prompt="Create a 2-week beginner Python course for me",
        ),
        ArticlePlanOutput(
            id="personalized-learning-plan",
            title="How to Build a Personalised Learning Plan",
            primary_keyword="personalized learning plan",
            secondary_keywords=[],
            search_intent="informational",
            article_type="standard",
            target_audience="self-improvers",
            angle="timeframe and daily minutes are the two variables that matter",
            meta_description="Build a personalised learning plan that actually works.",
            suggested_headings=["H2: Start with time"],
            cta_prompt="",
        ),
    ])

    research_brief = "Competitors: Duolingo, Coursera. Pain points: no personalised pacing."

    with patch("agents.seo_agent.create_react_agent") as mock_create:
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_gather_result)
        mock_create.return_value = mock_agent

        with patch("agents.seo_agent.get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=fake_synthesis)
            mock_llm.with_structured_output.return_value = mock_llm
            mock_llm_fn.return_value = mock_llm

            with patch("agents.seo_agent.seo_synthesis_prompt") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                entries = await run_seo_agent(research_brief, existing_ids=set())

    assert len(entries) == 4
    assert entries[0].id == "learn-spanish-30-days"
    assert entries[0].article_type == ArticleType.topic_teaser
    assert entries[1].article_type == ArticleType.standard


async def test_writing_agent_saves_draft(tmp_data_dir, sample_calendar_entry, sample_product_facts):
    from agents.writing_agent import run_writing_agent
    from output_schemas import ArticleOutput

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# The Feynman Technique\n\nYou can learn anything...",
    )

    with patch("agents.writing_agent.run_writing_chain", new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = fake_article
        with patch("agents.writing_agent.DRAFTS_DIR", tmp_data_dir / "drafts"):
            draft_path, article = await run_writing_agent(sample_calendar_entry, sample_product_facts)

    assert draft_path.exists()
    content = draft_path.read_text()
    assert "title:" in content
    assert "The Feynman Technique" in content
    assert article.markdown_content == fake_article.markdown_content


def test_remove_em_dashes_space_both_sides():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("learning — which") == "learning, which"


def test_remove_em_dashes_no_spaces():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("learning—which") == "learning, which"


def test_remove_em_dashes_space_before_only():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("learning —which") == "learning, which"


def test_remove_em_dashes_multiple():
    from agents.writing_agent import _remove_em_dashes
    result = _remove_em_dashes("fast — effective — proven")
    assert result == "fast, effective, proven"


def test_remove_em_dashes_no_emdash():
    from agents.writing_agent import _remove_em_dashes
    assert _remove_em_dashes("no emdash here") == "no emdash here"


async def test_writing_agent_strips_em_dashes_from_saved_draft(tmp_data_dir, sample_calendar_entry, sample_product_facts):
    from agents.writing_agent import run_writing_agent
    from output_schemas import ArticleOutput

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="Learn fast — and remember more — every day.",
    )

    with patch("agents.writing_agent.run_writing_chain", new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = fake_article
        with patch("agents.writing_agent.DRAFTS_DIR", tmp_data_dir / "drafts"):
            draft_path, _ = await run_writing_agent(sample_calendar_entry, sample_product_facts)

    content = draft_path.read_text()
    assert "—" not in content
    assert "Learn fast, and remember more, every day." in content
