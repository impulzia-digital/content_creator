"""Gemini native image generation provider."""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO

from django.conf import settings
from google import genai
from google.genai import types
from PIL import Image

from apps.integrations.base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)

_COST_PER_IMAGE = {
    "gemini-2.5-flash-image": {"1K": 0.039},
    "gemini-3.1-flash-image-preview": {"512": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
    "gemini-3-pro-image-preview": {"1K": 0.134, "2K": 0.134, "4K": 0.240},
}


class GeminiImageProvider(ImageProvider):
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        model = request.model or getattr(settings, "GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
        aspect_ratio = _resolve_aspect_ratio(request.width, request.height)
        image_size = _resolve_image_size(request.width, request.height)
        desired_content_type = _resolve_output_mime_type(request.output_format)

        prompt = request.prompt
        if request.negative_prompt:
            prompt = f"{prompt}\n\nAvoid: {request.negative_prompt}"

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                ),
            ),
        )

        image_bytes, detected_content_type = _extract_images(response, desired_content_type)

        return ImageGenerationResponse(
            image_bytes=image_bytes,
            model=getattr(response, "model_version", model) or model,
            cost_usd=_calculate_cost(model, image_size, len(image_bytes)),
            width=request.width,
            height=request.height,
            content_type=detected_content_type,
            raw_response=_dump_response(response),
        )


def _extract_images(
    response: types.GenerateContentResponse,
    requested_content_type: str,
) -> tuple[list[bytes], str]:
    images: list[bytes] = []
    detected_content_type = requested_content_type

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            if not inline_data:
                continue

            raw_data = getattr(inline_data, "data", None)
            if not raw_data:
                continue

            mime_type = getattr(inline_data, "mime_type", None) or requested_content_type
            if isinstance(raw_data, str):
                raw_data = base64.b64decode(raw_data)
            elif isinstance(raw_data, memoryview):
                raw_data = raw_data.tobytes()

            image_data = bytes(raw_data)
            if mime_type != requested_content_type:
                image_data = _convert_image_bytes(image_data, requested_content_type)
                mime_type = requested_content_type

            images.append(image_data)
            detected_content_type = mime_type

    return images, detected_content_type


def _convert_image_bytes(data: bytes, target_content_type: str) -> bytes:
    image = Image.open(BytesIO(data))
    output = BytesIO()
    if target_content_type == "image/jpeg":
        image = image.convert("RGB")
        image.save(output, format="JPEG", quality=92)
    else:
        image.save(output, format="PNG")
    return output.getvalue()


def _resolve_aspect_ratio(width: int, height: int) -> str:
    candidates = {
        "1:1": 1.0,
        "2:3": 2 / 3,
        "3:2": 3 / 2,
        "3:4": 3 / 4,
        "4:3": 4 / 3,
        "4:5": 4 / 5,
        "5:4": 5 / 4,
        "9:16": 9 / 16,
        "16:9": 16 / 9,
        "21:9": 21 / 9,
    }
    requested = width / height if height else 1.0
    return min(candidates, key=lambda ratio: abs(candidates[ratio] - requested))


def _resolve_image_size(width: int, height: int) -> str:
    largest_dimension = max(width, height)
    if largest_dimension <= 1024:
        return "1K"
    if largest_dimension <= 2048:
        return "2K"
    return "4K"


def _resolve_output_mime_type(output_format: str) -> str:
    normalized = output_format.lower().replace("jpg", "jpeg")
    return f"image/{normalized}"


def _calculate_cost(model: str, image_size: str, image_count: int) -> float:
    if image_count == 0:
        return 0.0
    rates = _COST_PER_IMAGE.get(model, {})
    unit_cost = rates.get(image_size) or rates.get("1K") or 0.0
    return unit_cost * image_count


def _dump_response(response: types.GenerateContentResponse) -> dict:
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", exclude_none=True)
    return {}