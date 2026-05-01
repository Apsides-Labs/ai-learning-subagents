import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_generate_blog_image_returns_bytes():
    from services.image_service import generate_blog_image

    fake_image_bytes = b"\x89PNG\r\n\x1a\n fake image data"

    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json="iVBORw0KGgo=")]

    with patch("services.image_service.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await generate_blog_image(
            title="Tutorial Hell",
            article_summary="How to escape tutorial hell.",
            key_takeaway="Build small projects instead of watching videos.",
        )

    assert result is not None
    assert isinstance(result, bytes)
    mock_client.images.generate.assert_called_once()
    call_kwargs = mock_client.images.generate.call_args[1]
    assert call_kwargs["model"] == "gpt-image-2"
    assert call_kwargs["size"] == "1536x1024"
    assert "Tutorial Hell" in call_kwargs["prompt"]


async def test_generate_blog_image_returns_none_on_failure():
    from services.image_service import generate_blog_image

    with patch("services.image_service.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(side_effect=Exception("API rate limit"))
        mock_client_cls.return_value = mock_client

        result = await generate_blog_image(
            title="Test",
            article_summary="Summary.",
            key_takeaway="Takeaway.",
        )

    assert result is None


async def test_generate_blog_image_interpolates_prompt():
    from services.image_service import generate_blog_image

    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json="iVBORw0KGgo=")]

    with patch("services.image_service.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.images.generate = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await generate_blog_image(
            title="Spaced Repetition",
            article_summary="A guide to spaced repetition.",
            key_takeaway="Review before you forget.",
        )

    call_kwargs = mock_client.images.generate.call_args[1]
    assert "Spaced Repetition" in call_kwargs["prompt"]
    assert "A guide to spaced repetition." in call_kwargs["prompt"]
    assert "Review before you forget." in call_kwargs["prompt"]
