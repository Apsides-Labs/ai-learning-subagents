import base64
import logging
from pathlib import Path

import openai

from config import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "md" / "chains" / "blog_image.md"


async def generate_blog_image(
    title: str,
    article_summary: str,
    key_takeaway: str,
) -> bytes | None:
    """Generate a hero image for a blog post. Returns PNG bytes or None on failure."""
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.format(
            title=title,
            article_summary=article_summary,
            key_takeaway=key_takeaway,
        )

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.images.generate(
            model="gpt-image-2",
            prompt=prompt,
            size="1536x1024",
            response_format="b64_json",
            n=1,
        )

        b64_data = response.data[0].b64_json
        return base64.b64decode(b64_data)

    except Exception:
        logger.warning("Blog image generation failed", exc_info=True)
        return None
