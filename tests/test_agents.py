import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


async def test_research_agent_returns_product_facts_and_brief():
    from agents.research_agent import run_setup_research

    gathered_data = "Codebase: courses have knowledge_level, daily_minutes. Competitor Duolingo: gamified language app."
    fake_gather_result = {"messages": [AIMessage(content=gathered_data)]}

    from output_schemas import ResearchSetupOutput, CompetitorOutput, ProductFactOutput
    fake_synthesis = ResearchSetupOutput(
        competitors=[
            CompetitorOutput(
                name="Duolingo",
                url="https://duolingo.com",
                positioning="gamified language",
                target_audience="casual learners",
                content_gaps=["no custom topics"],
            )
        ],
        product_facts=[
            ProductFactOutput(
                fact="Users set daily learning time (default: 20 minutes)",
                source_file="app/models/course.py",
            )
        ],
    )

    with patch("agents.research_agent.create_agent") as mock_create:
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_gather_result)
        mock_create.return_value = mock_agent

        with patch("agents.research_agent.get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=fake_synthesis)
            mock_llm.with_structured_output.return_value = mock_llm
            mock_llm_fn.return_value = mock_llm

            with patch("agents.research_agent.research_setup_synthesis_prompt") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                product_facts, competitor_profiles = await run_setup_research("/fake/codebase")

    assert "Users set daily learning time" in product_facts
    assert "Duolingo" in competitor_profiles


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
            blog_category="Study Methods",
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
            blog_category="Learning Science",
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
            blog_category="Study Methods",
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
            blog_category="Productivity",
        ),
    ])

    research_brief = "Competitors: Duolingo, Coursera. Pain points: no personalised pacing."

    with patch("agents.seo_agent.create_agent") as mock_create:
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
        article_summary="A guide to using the Feynman Technique to learn programming concepts faster.",
        key_takeaway="Explaining a concept in simple terms reveals what you actually understand.",
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
        article_summary="Tips for learning faster and retaining more.",
        key_takeaway="Spacing your practice sessions beats cramming every time.",
    )

    with patch("agents.writing_agent.run_writing_chain", new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = fake_article
        with patch("agents.writing_agent.DRAFTS_DIR", tmp_data_dir / "drafts"):
            draft_path, _ = await run_writing_agent(sample_calendar_entry, sample_product_facts)

    content = draft_path.read_text()
    assert "—" not in content
    assert "Learn fast, and remember more, every day." in content


async def test_research_agent_run_market_research():
    from agents.research_agent import run_market_research
    from output_schemas import MarketBriefOutput, PainPointOutput, ContentOpportunityOutput

    gathered_data = "Pain: no personalised pacing. Opportunity: Feynman for programmers."
    fake_gather_result = {"messages": [AIMessage(content=gathered_data)]}

    fake_synthesis = MarketBriefOutput(
        pain_points=[
            PainPointOutput(
                statement="no personalised pacing",
                sources=["Reddit r/languagelearning"],
                intensity="high",
                frequency="recurring",
                content_addressable=True,
            )
        ],
        content_opportunities=[
            ContentOpportunityOutput(
                angle="Feynman technique for programmers",
                addresses_pain_point="no personalised pacing",
                competitor_gap="Duolingo",
                why_now="gap in competitor content",
                article_type_hint="standard",
            )
        ],
    )

    with patch("agents.research_agent.create_agent") as mock_create:
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_gather_result)
        mock_create.return_value = mock_agent

        with patch("agents.research_agent.get_llm") as mock_llm_fn:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=fake_synthesis)
            mock_llm.with_structured_output.return_value = mock_llm
            mock_llm_fn.return_value = mock_llm

            with patch("agents.research_agent.research_market_synthesis_prompt") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                market_brief = await run_market_research("**Duolingo** competitor profile")

    assert "no personalised pacing" in market_brief
    assert "Feynman technique for programmers" in market_brief


async def test_orchestrator_setup(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_setup
    from services import file_service

    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "COMPETITOR_PROFILES_PATH", tmp_data_dir / "competitor_profiles.md")

    with patch("agents.orchestrator.run_setup_research", new_callable=AsyncMock) as mock_setup:
        mock_setup.return_value = ("- Users set daily learning time", "**Duolingo** (duolingo.com)")
        await run_setup()

    assert (tmp_data_dir / "product_facts.md").exists()
    assert "Users set daily learning time" in (tmp_data_dir / "product_facts.md").read_text()
    assert (tmp_data_dir / "competitor_profiles.md").exists()


async def test_orchestrator_weekly_batch(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_weekly_batch
    from services import calendar_service, file_service

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "COMPETITOR_PROFILES_PATH", tmp_data_dir / "competitor_profiles.md")
    monkeypatch.setattr(file_service, "MARKET_BRIEF_PATH", tmp_data_dir / "market_brief.md")

    await file_service.write_text(tmp_data_dir / "product_facts.md", "- fact")
    await file_service.write_text(tmp_data_dir / "competitor_profiles.md", "**Duolingo**")

    from models.article import ArticleType, ContentCalendarEntry
    fake_entries = [
        ContentCalendarEntry(
            id=f"article-{i}", title=f"Article {i}", primary_keyword=f"kw {i}",
            article_type=ArticleType.standard, target_audience="learners",
            angle="angle", meta_description="desc",
        )
        for i in range(4)
    ]

    with patch("agents.orchestrator.run_market_research", new_callable=AsyncMock) as mock_market:
        mock_market.return_value = "## Market Brief\n- pain point"
        with patch("agents.orchestrator.run_seo_agent", new_callable=AsyncMock) as mock_seo:
            mock_seo.return_value = fake_entries
            titles = await run_weekly_batch()

    assert len(titles) == 4
    assert (tmp_data_dir / "market_brief.md").exists()
    calendar = await calendar_service.load_calendar()
    assert len(calendar) == 4


async def test_orchestrator_weekly_batch_auto_setup(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_weekly_batch
    from services import calendar_service, file_service

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "COMPETITOR_PROFILES_PATH", tmp_data_dir / "competitor_profiles.md")
    monkeypatch.setattr(file_service, "MARKET_BRIEF_PATH", tmp_data_dir / "market_brief.md")

    from models.article import ArticleType, ContentCalendarEntry
    fake_entries = [
        ContentCalendarEntry(
            id=f"a-{i}", title=f"A {i}", primary_keyword=f"kw {i}",
            article_type=ArticleType.standard, target_audience="learners",
            angle="angle", meta_description="desc",
        )
        for i in range(4)
    ]

    with patch("agents.orchestrator.run_setup_research", new_callable=AsyncMock) as mock_setup:
        mock_setup.return_value = ("- fact", "**Competitor**")
        with patch("agents.orchestrator.run_market_research", new_callable=AsyncMock) as mock_market:
            mock_market.return_value = "## Market Brief"
            with patch("agents.orchestrator.run_seo_agent", new_callable=AsyncMock) as mock_seo:
                mock_seo.return_value = fake_entries
                titles = await run_weekly_batch()

    mock_setup.assert_called_once()
    assert len(titles) == 4


async def test_orchestrator_article_mode_clean(tmp_data_dir, sample_calendar_entry, sample_product_facts, monkeypatch):
    from agents.orchestrator import run_article
    from services import calendar_service, file_service
    from output_schemas import ArticleOutput, FactCheckOutput

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    monkeypatch.setattr(file_service, "PRODUCT_FACTS_PATH", tmp_data_dir / "product_facts.md")
    monkeypatch.setattr(file_service, "DRAFTS_DIR", tmp_data_dir / "drafts")

    await file_service.write_text(tmp_data_dir / "product_facts.md", sample_product_facts)
    await calendar_service.add_entries([sample_calendar_entry])

    fake_article = ArticleOutput(
        title=sample_calendar_entry.title,
        primary_keyword=sample_calendar_entry.primary_keyword,
        meta_description=sample_calendar_entry.meta_description,
        markdown_content="# Feynman Technique\n\nLearn anything.",
        article_summary="A guide to the Feynman Technique for programmers.",
        key_takeaway="Teaching what you learn is the fastest way to master it.",
    )
    fake_fact_check = FactCheckOutput(passed=True, items=[])
    fake_image = b"fake png bytes"

    with patch("agents.orchestrator.run_writing_agent", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = (tmp_data_dir / "drafts" / "draft.md", fake_article)
        with patch("agents.orchestrator.run_fact_check_chain", new_callable=AsyncMock) as mock_fc:
            mock_fc.return_value = fake_fact_check
            with patch("agents.orchestrator.generate_blog_image", new_callable=AsyncMock) as mock_img:
                mock_img.return_value = fake_image
                with patch("agents.orchestrator.create_blog_pr", new_callable=AsyncMock) as mock_pr:
                    mock_pr.return_value = None
                    status, draft_path, pr_url = await run_article()

    from models.article import ArticleStatus
    assert status == ArticleStatus.ready_for_review

    # Verify image generation was called with article fields
    mock_img.assert_called_once_with(
        title=fake_article.title,
        article_summary=fake_article.article_summary,
        key_takeaway=fake_article.key_takeaway,
    )

    # Verify image bytes were passed to create_blog_pr
    mock_pr.assert_called_once()
    pr_call_kwargs = mock_pr.call_args
    # image_bytes should be passed as keyword arg
    assert pr_call_kwargs[1].get("image_bytes") == fake_image


async def test_orchestrator_article_mode_no_planned(tmp_data_dir, monkeypatch):
    from agents.orchestrator import run_article
    from services import calendar_service

    monkeypatch.setattr(calendar_service, "CALENDAR_PATH", tmp_data_dir / "content_calendar.json")
    status, draft_path, pr_url = await run_article()
    assert status is None
    assert draft_path is None
    assert pr_url is None
