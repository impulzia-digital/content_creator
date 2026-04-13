"""OpenAI image generation provider (DALL-E)."""

from __future__ import annotations

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


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        size = f"{request.width}x{request.height}"
        model = request.model or "gpt-image-1"

        response = await self._client.images.generate(
            model=model,
            prompt=request.prompt,
            n=request.num_images,
            size=size,
        )

        urls = [img.url for img in response.data if img.url]

        cost = _COST_PER_IMAGE.get(model, {}).get(size, 0.04) * len(urls)

        return ImageGenerationResponse(
            image_urls=urls,
            model=model,
            cost_usd=cost,
            raw_response={"data": [{"url": u} for u in urls]},
        )
