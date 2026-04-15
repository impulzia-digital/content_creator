"""Google Veo video generation provider."""

from __future__ import annotations

import asyncio
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

from apps.integrations.base import (
    VideoGenerationRequest,
    VideoGenerationResponse,
    VideoProvider,
)


class VeoVideoProvider(VideoProvider):
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)
        self._poll_interval = float(getattr(settings, "VEO_POLL_INTERVAL_SECONDS", 10.0))
        self._max_wait = float(getattr(settings, "VEO_MAX_WAIT_SECONDS", 600.0))

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        if not request.prompt.strip():
            raise ValueError("Veo requiere un prompt de video no vacío")

        model = request.model or getattr(settings, "VEO_VIDEO_MODEL", "veo-3.1-generate-preview")
        prompt = _build_prompt(request.prompt, request.negative_prompt)
        aspect_ratio = _resolve_aspect_ratio(request.width, request.height)
        duration_seconds = _normalize_duration(
            request.duration_seconds,
            getattr(settings, "VEO_VIDEO_RESOLUTION", "720p"),
        )
        resolution = _normalize_resolution(
            getattr(settings, "VEO_VIDEO_RESOLUTION", "720p"),
            duration_seconds,
        )
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            resolution=resolution,
            person_generation=getattr(settings, "VEO_PERSON_GENERATION", "allow_all"),
        )

        operation = await asyncio.to_thread(
            self._client.models.generate_videos,
            model=model,
            prompt=prompt,
            config=config,
        )
        operation = await self._poll_operation(operation)

        response = getattr(operation, "response", None) or getattr(operation, "result", None)
        generated_videos = getattr(response, "generated_videos", None) or []
        if not generated_videos:
            raise RuntimeError("Veo no devolvió videos generados")

        generated_video = generated_videos[0]
        video = generated_video.video
        video_bytes = await asyncio.to_thread(self._client.files.download, file=video)

        return VideoGenerationResponse(
            video_url=getattr(video, "uri", "") or "",
            video_bytes=bytes(video_bytes),
            duration_seconds=float(duration_seconds),
            model=model,
            cost_usd=0.0,
            content_type=getattr(video, "mime_type", None) or "video/mp4",
            raw_response=_dump_operation(operation),
        )

    async def _poll_operation(self, operation: Any) -> Any:
        elapsed = 0.0
        current = operation
        while not getattr(current, "done", False):
            if elapsed > self._max_wait:
                raise TimeoutError("La operación de Veo excedió el tiempo máximo de espera")
            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval
            current = await asyncio.to_thread(self._client.operations.get, current)
        return current


def _resolve_aspect_ratio(width: int, height: int) -> str:
    return "9:16" if height >= width else "16:9"


def _build_prompt(prompt: str, negative_prompt: str) -> str:
    cleaned_prompt = prompt.strip()
    cleaned_negative_prompt = negative_prompt.strip()
    if not cleaned_negative_prompt:
        return cleaned_prompt
    return f"{cleaned_prompt}\n\nAvoid: {cleaned_negative_prompt}"


def _normalize_duration(duration_seconds: float, resolution: str) -> int:
    if resolution in {"1080p", "4k"}:
        return 8
    if duration_seconds <= 4:
        return 4
    if duration_seconds <= 6:
        return 6
    return 8


def _normalize_resolution(resolution: str, duration_seconds: int) -> str:
    normalized = str(resolution).strip().lower()
    if normalized in {"1080", "1080p", "fullhd"}:
        return "1080p" if duration_seconds == 8 else "720p"
    if normalized in {"4k", "2160p"}:
        return "4k" if duration_seconds == 8 else "720p"
    return "720p"


def _dump_operation(operation: Any) -> dict[str, Any]:
    model_dump = getattr(operation, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", exclude_none=True)
    return {}