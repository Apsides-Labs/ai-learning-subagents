from enum import StrEnum
from typing import Optional
from pydantic import BaseModel


class ArticleStatus(StrEnum):
    planned = "planned"
    in_progress = "in_progress"
    ready_for_review = "ready_for_review"
    needs_review_flagged = "needs_review_flagged"
    published = "published"


class ArticleType(StrEnum):
    standard = "standard"
    topic_teaser = "topic_teaser"


class ContentCalendarEntry(BaseModel):
    id: str
    status: ArticleStatus = ArticleStatus.planned
    title: str
    primary_keyword: str
    secondary_keywords: list[str] = []
    search_intent: str = "informational"
    article_type: ArticleType
    target_audience: str
    angle: str
    meta_description: str
    suggested_headings: list[str] = []
    cta_prompt: str = ""
    blog_category: str = "Study Methods"
    draft_path: Optional[str] = None
