"""Creatomate video generation provider."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from django.conf import settings

from apps.integrations.base import (
    VideoGenerationRequest,
    VideoGenerationResponse,
    VideoProvider,
)

logger = logging.getLogger(__name__)

_SUCCESS_STATUSES = {"completed", "done", "finished", "succeeded", "success"}
_FAILURE_STATUSES = {"canceled", "cancelled", "error", "failed"}


class CreatomateVideoProvider(VideoProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float = 60.0):
        self._api_key = api_key or settings.CREATOMATE_API_KEY
        self._base_url = (base_url or settings.CREATOMATE_API_BASE_URL or "https://api.creatomate.com/v2").rstrip("/")
        self._timeout = timeout
        self._poll_interval = float(getattr(settings, "CREATOMATE_POLL_INTERVAL_SECONDS", 5.0))
        self._max_wait = float(getattr(settings, "CREATOMATE_MAX_WAIT_SECONDS", 600.0))

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        if not self._api_key:
            raise ValueError("CREATOMATE_API_KEY no configurado")

        payload = _build_payload(request)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/renders",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            render = _coerce_render_payload(response.json())

            render_id = _extract_render_id(render)
            if render_id and not _is_terminal(render):
                render = await self._poll_render(client, render_id)

        status = _normalize_status(render)
        if status in _FAILURE_STATUSES:
            raise RuntimeError(_extract_error(render) or "Creatomate render falló")

        video_url = _extract_video_url(render)
        if not video_url:
            raise RuntimeError("Creatomate no devolvió una URL de video utilizable")

        return VideoGenerationResponse(
            video_url=video_url,
            thumbnail_url=_extract_thumbnail_url(render),
            duration_seconds=float(render.get("duration") or request.duration_seconds or 0.0),
            model=request.model or getattr(settings, "CREATOMATE_VIDEO_MODEL", "creatomate-renderscript"),
            cost_usd=_extract_cost(render),
            content_type="video/mp4",
            thumbnail_content_type="image/jpeg",
            raw_response=render,
        )

    async def _poll_render(self, client: httpx.AsyncClient, render_id: str) -> dict[str, Any]:
        elapsed = 0.0
        while elapsed <= self._max_wait:
            response = await client.get(
                f"{self._base_url}/renders/{render_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            render = _coerce_render_payload(response.json())
            if _is_terminal(render):
                return render
            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval

        raise TimeoutError(f"Creatomate render {render_id} excedió el tiempo máximo de espera")


def _build_payload(request: VideoGenerationRequest) -> dict[str, Any]:
    if request.template_id:
        return {
            "template_id": request.template_id,
            "modifications": request.template_params,
            "output_format": request.output_format,
        }

    if request.render_spec:
        payload = dict(request.render_spec)
        payload.setdefault("output_format", request.output_format)
        return payload

    raise ValueError("Creatomate requiere template_id o render_spec")


def _coerce_render_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload else {}
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_render_id(render: dict[str, Any]) -> str:
    value = render.get("id") or render.get("render_id") or render.get("uuid")
    return str(value) if value else ""


def _normalize_status(render: dict[str, Any]) -> str:
    status = render.get("status") or render.get("state") or render.get("render_status") or ""
    return str(status).strip().lower()


def _is_terminal(render: dict[str, Any]) -> bool:
    status = _normalize_status(render)
    if not status:
        return bool(_extract_video_url(render))
    return status in _SUCCESS_STATUSES or status in _FAILURE_STATUSES


def _extract_video_url(render: dict[str, Any]) -> str:
    for key in ("url", "video_url", "download_url", "output_url"):
        value = render.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_thumbnail_url(render: dict[str, Any]) -> str:
    for key in ("snapshot_url", "thumbnail_url", "preview_url"):
        value = render.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_error(render: dict[str, Any]) -> str:
    for key in ("error", "error_message", "message"):
        value = render.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_cost(render: dict[str, Any]) -> float:
    for key in ("cost", "cost_usd", "credits_cost"):
        value = render.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0