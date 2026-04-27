"""OpenAI image generation provider (DALL-E)."""

from __future__ import annotations

import base64
import logging
import math

from django.conf import settings
from openai import AsyncOpenAI

from apps.integrations.base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)

logger = logging.getLogger(__name__)

_DEFAULT_GPT_IMAGE_QUALITY = "medium"
_GPT_IMAGE_2_MULTIPLE = 16
_GPT_IMAGE_2_MAX_EDGE = 3840
_GPT_IMAGE_2_MIN_PIXELS = 655_360
_GPT_IMAGE_2_MAX_PIXELS = 8_294_400
_GPT_IMAGE_2_MAX_ASPECT_RATIO = 3.0

_GPT_IMAGE_COST_PER_IMAGE = {
    "gpt-image-2": {
        "low": {"1024x1024": 0.006, "1024x1536": 0.005, "1536x1024": 0.005},
        "medium": {"1024x1024": 0.053, "1024x1536": 0.041, "1536x1024": 0.041},
        "high": {"1024x1024": 0.211, "1024x1536": 0.165, "1536x1024": 0.165},
    },
    "gpt-image-1.5": {
        "low": {"1024x1024": 0.009, "1024x1536": 0.013, "1536x1024": 0.013},
        "medium": {"1024x1024": 0.034, "1024x1536": 0.050, "1536x1024": 0.050},
        "high": {"1024x1024": 0.133, "1024x1536": 0.200, "1536x1024": 0.200},
    },
    "gpt-image-1": {
        "low": {"1024x1024": 0.011, "1024x1536": 0.016, "1536x1024": 0.016},
        "medium": {"1024x1024": 0.042, "1024x1536": 0.063, "1536x1024": 0.063},
        "high": {"1024x1024": 0.167, "1024x1536": 0.250, "1536x1024": 0.250},
    },
    "gpt-image-1-mini": {
        "low": {"1024x1024": 0.005, "1024x1536": 0.006, "1536x1024": 0.006},
        "medium": {"1024x1024": 0.011, "1024x1536": 0.015, "1536x1024": 0.015},
        "high": {"1024x1024": 0.036, "1024x1536": 0.052, "1536x1024": 0.052},
    },
}

_DALL_E_3_COST_PER_IMAGE = {
    "standard": {"1024x1024": 0.040, "1024x1792": 0.080, "1792x1024": 0.080},
}


def _content_type_for_format(output_format: str) -> str:
    return {
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(output_format, "image/jpeg")


def _round_to_multiple(value: float, *, multiple: int) -> int:
    rounded = int(round(value / multiple) * multiple)
    return max(multiple, rounded)


def _scale_dimensions(width: int, height: int, scale: float) -> tuple[int, int]:
    return (
        _round_to_multiple(width * scale, multiple=_GPT_IMAGE_2_MULTIPLE),
        _round_to_multiple(height * scale, multiple=_GPT_IMAGE_2_MULTIPLE),
    )


def _normalize_gpt_image_2_size(width: int, height: int) -> tuple[int, int]:
    width = _round_to_multiple(max(width, _GPT_IMAGE_2_MULTIPLE), multiple=_GPT_IMAGE_2_MULTIPLE)
    height = _round_to_multiple(max(height, _GPT_IMAGE_2_MULTIPLE), multiple=_GPT_IMAGE_2_MULTIPLE)

    longest_edge = max(width, height)
    if longest_edge > _GPT_IMAGE_2_MAX_EDGE:
        width, height = _scale_dimensions(width, height, _GPT_IMAGE_2_MAX_EDGE / longest_edge)

    aspect_ratio = max(width / height, height / width)
    if aspect_ratio > _GPT_IMAGE_2_MAX_ASPECT_RATIO:
        if width > height:
            width = _round_to_multiple(
                height * _GPT_IMAGE_2_MAX_ASPECT_RATIO,
                multiple=_GPT_IMAGE_2_MULTIPLE,
            )
        else:
            height = _round_to_multiple(
                width * _GPT_IMAGE_2_MAX_ASPECT_RATIO,
                multiple=_GPT_IMAGE_2_MULTIPLE,
            )

    pixels = width * height
    if pixels > _GPT_IMAGE_2_MAX_PIXELS:
        width, height = _scale_dimensions(width, height, math.sqrt(_GPT_IMAGE_2_MAX_PIXELS / pixels))

    pixels = width * height
    if pixels < _GPT_IMAGE_2_MIN_PIXELS:
        width, height = _scale_dimensions(width, height, math.sqrt(_GPT_IMAGE_2_MIN_PIXELS / pixels))
        longest_edge = max(width, height)
        if longest_edge > _GPT_IMAGE_2_MAX_EDGE:
            width, height = _scale_dimensions(width, height, _GPT_IMAGE_2_MAX_EDGE / longest_edge)

    width = min(width, _GPT_IMAGE_2_MAX_EDGE)
    height = min(height, _GPT_IMAGE_2_MAX_EDGE)
    return width, height


def _normalize_size(width: int, height: int, model: str) -> tuple[int, int]:
    """Ajusta dimensiones al set soportado por OpenAI sin romper la orientación."""
    if model == "gpt-image-2":
        normalized = _normalize_gpt_image_2_size(width, height)
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

    supported_sizes = [tuple(map(int, size.split("x"))) for size in _supported_sizes_for_model(model)]
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


def _supported_sizes_for_model(model: str) -> tuple[str, ...]:
    if model in _GPT_IMAGE_COST_PER_IMAGE:
        return tuple(_GPT_IMAGE_COST_PER_IMAGE[model][_DEFAULT_GPT_IMAGE_QUALITY].keys())
    if model == "dall-e-3":
        return tuple(_DALL_E_3_COST_PER_IMAGE["standard"].keys())
    return ()


def _parse_size(size: str) -> tuple[int, int]:
    width, height = size.split("x", maxsplit=1)
    return int(width), int(height)


def _estimate_gpt_image_2_unit_cost(size: str) -> float:
    reference_costs = _GPT_IMAGE_COST_PER_IMAGE["gpt-image-2"][_DEFAULT_GPT_IMAGE_QUALITY]
    exact_cost = reference_costs.get(size)
    if exact_cost is not None:
        return exact_cost

    width, height = _parse_size(size)
    requested_pixels = width * height
    requested_ratio = width / height

    reference_size, reference_cost = min(
        reference_costs.items(),
        key=lambda item: abs((_parse_size(item[0])[0] / _parse_size(item[0])[1]) - requested_ratio),
    )
    reference_width, reference_height = _parse_size(reference_size)
    pixel_scale = requested_pixels / (reference_width * reference_height)
    return reference_cost * pixel_scale


def _calculate_cost(model: str, size: str, image_count: int) -> float:
    if image_count == 0:
        return 0.0

    if model == "gpt-image-2":
        return _estimate_gpt_image_2_unit_cost(size) * image_count

    if model in _GPT_IMAGE_COST_PER_IMAGE:
        unit_cost = _GPT_IMAGE_COST_PER_IMAGE[model][_DEFAULT_GPT_IMAGE_QUALITY].get(size, 0.0)
        return unit_cost * image_count

    if model == "dall-e-3":
        unit_cost = _DALL_E_3_COST_PER_IMAGE["standard"].get(size, 0.0)
        return unit_cost * image_count

    return 0.0


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        model = request.model or getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-2")
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
            request_kwargs["quality"] = _DEFAULT_GPT_IMAGE_QUALITY
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
        cost = _calculate_cost(model, size, image_count)

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
                "quality": request_kwargs.get("quality"),
                "output_format": output_format,
            },
        )
