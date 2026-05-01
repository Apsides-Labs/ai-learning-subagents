import base64
import logging
from pathlib import Path

import openai

from config import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "md" / "chains" / "blog_image.md"


_MODELS = [
    {"model": "gpt-image-2", "size": "1536x1024", "output_format": "png"},
    {"model": "gpt-image-1", "size": "1536x1024", "output_format": "png"},
    {"model": "dall-e-3", "size": "1792x1024", "response_format": "b64_json"},
]


async def generate_blog_image(
    title: str,
    article_summary: str,
    key_takeaway: str,
) -> bytes | None:
    """Generate a hero image for a blog post. Returns PNG bytes or None on failure."""
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        title=title,
        article_summary=article_summary,
        key_takeaway=key_takeaway,
    )

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    for model_cfg in _MODELS:
        try:
            logger.info("Trying image model: %s", model_cfg["model"])
            response = await client.images.generate(
                prompt=prompt,
                n=1,
                **model_cfg,
            )

            b64_data = response.data[0].b64_json
            return base64.b64decode(b64_data)

        except Exception:
            logger.warning("Image generation failed with %s", model_cfg["model"], exc_info=True)

    logger.warning("All image models failed, skipping hero image")
    return None
