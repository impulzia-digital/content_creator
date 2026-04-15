"""Imagen 4 image generation provider (Google)."""

from __future__ import annotations

import asyncio

from django.conf import settings
from google import genai
from google.genai import types

from apps.integrations.base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)

_COST_PER_IMAGE = {
    "imagen-4.0-ultra-generate-001": 0.060,
    "imagen-4.0-generate-001": 0.040,
    "imagen-4.0-fast-generate-001": 0.020,
}

_SUPPORTED_ASPECT_RATIOS = {"1:1", "3:4", "4:3", "9:16", "16:9"}


class Imagen4ImageProvider(ImageProvider):
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        model = request.model or "imagen-4.0-generate-001"
        aspect_ratio = _resolve_aspect_ratio(request.width, request.height)

        config = types.GenerateImagesConfig(
            number_of_images=request.num_images,
            aspect_ratio=aspect_ratio,
            person_generation="allow_adult",
        )

        response = await asyncio.to_thread(
            self._client.models.generate_images,
            model=model,
            prompt=request.prompt,
            config=config,
        )

        image_bytes: list[bytes] = []
        for gen_img in getattr(response, "generated_images", []) or []:
            img = getattr(gen_img, "image", None)
            if img is None:
                continue
            data = getattr(img, "image_bytes", None)
            if data is None:
                continue
            if isinstance(data, memoryview):
                data = data.tobytes()
            image_bytes.append(bytes(data))

        cost = _calculate_cost(model, len(image_bytes))

        return ImageGenerationResponse(
            image_bytes=image_bytes,
            model=model,
            cost_usd=cost,
            width=request.width,
            height=request.height,
            content_type="image/png",
            raw_response={"model": model, "image_count": len(image_bytes)},
        )


def _resolve_aspect_ratio(width: int, height: int) -> str:
    candidates = {
        "1:1": 1.0,
        "3:4": 3 / 4,
        "4:3": 4 / 3,
        "9:16": 9 / 16,
        "16:9": 16 / 9,
    }
    requested = width / height if height else 1.0
    return min(candidates, key=lambda r: abs(candidates[r] - requested))


def _resolve_image_size(width: int, height: int) -> str:
    return "2K" if max(width, height) > 1024 else "1K"


def _calculate_cost(model: str, image_count: int) -> float:
    if image_count == 0:
        return 0.0
    unit_cost = _COST_PER_IMAGE.get(model, 0.0)
    return unit_cost * image_count
