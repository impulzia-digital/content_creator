"""OpenAI image generation provider (DALL-E)."""

from __future__ import annotations

import base64
import logging

from django.conf import settings
from openai import AsyncOpenAI

from apps.integrations.base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)

logger = logging.getLogger(__name__)

_COST_PER_IMAGE = {
    "dall-e-3": {"1024x1024": 0.040, "1024x1792": 0.080, "1792x1024": 0.080},
    "gpt-image-1": {"1024x1024": 0.040, "1024x1536": 0.060, "1536x1024": 0.060},
}


def _content_type_for_format(output_format: str) -> str:
    return {
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(output_format, "image/jpeg")


def _normalize_size(width: int, height: int, model: str) -> tuple[int, int]:
    """Ajusta dimensiones al set soportado por OpenAI sin romper la orientación."""
    supported_sizes = [tuple(map(int, size.split("x"))) for size in _COST_PER_IMAGE.get(model, {})]
    if not supported_sizes:
        return width, height

    if (width, height) in supported_sizes:
        return width, height

    requested_ratio = width / height
    normalized = min(
        supported_sizes,
        key=lambda size: abs((size[0] / size[1]) - requested_ratio),
    )

    if normalized != (width, height):
        logger.info(
            "OpenAI images size %sx%s normalizado a %sx%s para el modelo %s",
            width,
            height,
            normalized[0],
            normalized[1],
            model,
        )

    return normalized


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        model = request.model or "gpt-image-1"
        width, height = _normalize_size(request.width, request.height, model)
        size = f"{width}x{height}"
        output_format = request.output_format or "jpeg"

        request_kwargs = {
            "model": model,
            "prompt": request.prompt,
            "n": request.num_images,
            "size": size,
        }
        if model.startswith("gpt-image"):
            request_kwargs["output_format"] = output_format

        response = await self._client.images.generate(
            **request_kwargs,
        )

        urls: list[str] = []
        image_bytes: list[bytes] = []
        raw_items: list[dict] = []
        for img in response.data:
            url = getattr(img, "url", None)
            if url:
                urls.append(url)
                raw_items.append({"url": url})
                continue

            b64_json = getattr(img, "b64_json", None)
            if b64_json:
                image_bytes.append(base64.b64decode(b64_json))
                raw_items.append({"b64_json": True})

        image_count = len(urls) + len(image_bytes)
        cost = _COST_PER_IMAGE.get(model, {}).get(size, 0.04) * max(image_count, request.num_images)

        return ImageGenerationResponse(
            image_urls=urls,
            image_bytes=image_bytes,
            model=model,
            cost_usd=cost,
            width=width,
            height=height,
            content_type=_content_type_for_format(output_format),
            raw_response={
                "data": raw_items,
                "size": size,
                "output_format": output_format,
            },
        )
