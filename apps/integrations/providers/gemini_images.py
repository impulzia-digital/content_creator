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

_LONG_CONTEXT_THRESHOLD = 200_000

_TEXT_COST_PER_1M = {
    "gemini-2.5-flash-image": {"input": 0.30, "output": 2.50},
    "gemini-3.1-flash-image-preview": {"input": 0.50, "output": 3.00},
    "gemini-3-pro-image-preview": {"input": 2.00, "output": 12.00},
}

_LONG_CONTEXT_TEXT_COST_PER_1M = {
    "gemini-3-pro-image-preview": {"input": 4.00, "output": 18.00},
}


class GeminiImageProvider(ImageProvider):
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        model = request.model or getattr(settings, "GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
        aspect_ratio = _resolve_aspect_ratio(request.width, request.height)
        image_size = _resolve_image_size(request.width, request.height, model)
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
                image_config=_build_image_config(model, aspect_ratio, image_size),
            ),
        )

        image_bytes, detected_content_type = _extract_images(response, desired_content_type)
        prompt_tokens, completion_tokens, thoughts_tokens = _extract_usage_metadata(response)

        return ImageGenerationResponse(
            image_bytes=image_bytes,
            model=getattr(response, "model_version", model) or model,
            cost_usd=_calculate_cost(
                model=model,
                image_size=image_size,
                image_count=len(image_bytes),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                thoughts_tokens=thoughts_tokens,
            ),
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
            if getattr(part, "thought", None) is True:
                continue

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


def _resolve_image_size(width: int, height: int, model: str) -> str:
    if model == "gemini-2.5-flash-image":
        return "1K"

    largest_dimension = max(width, height)
    if model == "gemini-3.1-flash-image-preview" and largest_dimension <= 512:
        return "512"
    if largest_dimension <= 1024:
        return "1K"
    if largest_dimension <= 2048:
        return "2K"
    return "4K"


def _build_image_config(model: str, aspect_ratio: str, image_size: str) -> types.ImageConfig:
    config_kwargs = {"aspect_ratio": aspect_ratio}
    if model != "gemini-2.5-flash-image":
        config_kwargs["image_size"] = image_size
    return types.ImageConfig(**config_kwargs)


def _resolve_output_mime_type(output_format: str) -> str:
    normalized = output_format.lower().replace("jpg", "jpeg")
    return f"image/{normalized}"


def _calculate_cost(
    model: str,
    image_size: str,
    image_count: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    thoughts_tokens: int = 0,
) -> float:
    rates = _COST_PER_IMAGE.get(model, {})
    unit_cost = rates.get(image_size) or rates.get("1K") or 0.0
    image_cost = unit_cost * image_count

    text_rates = _resolve_text_rates(model, prompt_tokens)
    text_cost = 0.0
    if text_rates:
        text_cost = (
            prompt_tokens * text_rates["input"] / 1_000_000
            + (completion_tokens + thoughts_tokens) * text_rates["output"] / 1_000_000
        )

    return image_cost + text_cost


def _extract_usage_metadata(response: types.GenerateContentResponse) -> tuple[int, int, int]:
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    thoughts_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
    return prompt_tokens, completion_tokens, thoughts_tokens


def _resolve_text_rates(model: str, prompt_tokens: int) -> dict[str, float]:
    if prompt_tokens > _LONG_CONTEXT_THRESHOLD and model in _LONG_CONTEXT_TEXT_COST_PER_1M:
        return _LONG_CONTEXT_TEXT_COST_PER_1M[model]
    return _TEXT_COST_PER_1M.get(model, {})


def _dump_response(response: types.GenerateContentResponse) -> dict:
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", exclude_none=True)
    return {}