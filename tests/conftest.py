import os
import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    (tmp_path / "drafts").mkdir()
    return tmp_path


@pytest.fixture
def sample_product_facts() -> str:
    return """## Draft and Arc — Product Facts

- Users create courses from a text prompt or by uploading a PDF
- Knowledge levels: beginner, intermediate, advanced
- Users set daily learning time (default: 20 minutes)
- Users set course duration in days (default: 14 days)
- Lesson types: concept, workshop, case_study, problem_set, project, deep_dive
- Learning domains: conceptual, procedural, technical, creative, physical, language, analytical
- Feynman technique: user explains a concept; AI scores and gives feedback
- Quiz assessments with multiple-choice questions and explanations
- Progress tracking: completed lessons, time spent per lesson
- Note-taking: one note per lesson per user
- Google OAuth login supported
- PDF upload: document is processed with RAG; lessons use it as context
"""


@pytest.fixture
def sample_calendar_entry():
    from models.article import ContentCalendarEntry, ArticleType
    return ContentCalendarEntry(
        id="feynman-technique-for-programmers",
        title="The Feynman Technique for Programmers: Learn Anything Faster",
        primary_keyword="feynman technique programming",
        secondary_keywords=["how to learn programming faster", "feynman method study"],
        article_type=ArticleType.standard,
        target_audience="developers who want to learn faster",
        angle="Draft and Arc's built-in Feynman prompts make this technique effortless",
        meta_description="Use the Feynman Technique to master any programming concept. Learn how it works and how to apply it today.",
        suggested_headings=[
            "H2: What is the Feynman Technique?",
            "H2: Why it works for technical concepts",
            "H2: How to apply it to programming",
            "H2: The shortcut",
        ],
        cta_prompt="Create a course that uses the Feynman Technique to teach me Python decorators",
    )
