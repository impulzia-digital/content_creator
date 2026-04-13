"""Interfaces base (ABC) para todos los proveedores."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


# ── Text Generation ──────────────────────────────────────────────


@dataclass
class TextGenerationRequest:
    system_prompt: str
    user_prompt: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000
    response_format: str | None = None  # "json_object" | None


@dataclass
class TextGenerationResponse:
    text: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw_response: dict = field(default_factory=dict)


class TextProvider(abc.ABC):
    @abc.abstractmethod
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        ...


# ── Image Generation ─────────────────────────────────────────────


@dataclass
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 1080
    height: int = 1350  # 4:5
    model: str = ""
    style: str = ""
    num_images: int = 1
    output_format: str = "jpeg"  # Instagram requiere JPEG


@dataclass
class ImageGenerationResponse:
    image_urls: list[str] = field(default_factory=list)
    model: str = ""
    cost_usd: float = 0.0
    seed: int | None = None
    raw_response: dict = field(default_factory=dict)


class ImageProvider(abc.ABC):
    @abc.abstractmethod
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        ...


# ── Video Generation ─────────────────────────────────────────────


@dataclass
class VideoGenerationRequest:
    # Template-based
    template_id: str = ""
    template_params: dict = field(default_factory=dict)
    # Generative
    prompt: str = ""
    # Common
    duration_seconds: float = 15.0
    width: int = 1080
    height: int = 1920  # 9:16 reel
    output_format: str = "mp4"


@dataclass
class VideoGenerationResponse:
    video_url: str = ""
    thumbnail_url: str = ""
    duration_seconds: float = 0.0
    model: str = ""
    cost_usd: float = 0.0
    raw_response: dict = field(default_factory=dict)


class VideoProvider(abc.ABC):
    @abc.abstractmethod
    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        ...


# ── Instagram Publishing ─────────────────────────────────────────


@dataclass
class InstagramMediaContainer:
    container_id: str
    status: str = "IN_PROGRESS"


@dataclass
class InstagramPublishResult:
    media_id: str = ""
    permalink: str = ""
    error: str = ""
    raw_response: dict = field(default_factory=dict)


class InstagramPublisher(abc.ABC):
    @abc.abstractmethod
    async def create_image_container(
        self, ig_user_id: str, image_url: str, caption: str, access_token: str
    ) -> InstagramMediaContainer:
        ...

    @abc.abstractmethod
    async def create_carousel_container(
        self,
        ig_user_id: str,
        children_container_ids: list[str],
        caption: str,
        access_token: str,
    ) -> InstagramMediaContainer:
        ...

    @abc.abstractmethod
    async def create_reel_container(
        self, ig_user_id: str, video_url: str, caption: str, access_token: str,
        thumb_offset_ms: int = 0,
    ) -> InstagramMediaContainer:
        ...

    @abc.abstractmethod
    async def check_container_status(
        self, container_id: str, access_token: str
    ) -> str:
        ...

    @abc.abstractmethod
    async def publish_container(
        self, ig_user_id: str, container_id: str, access_token: str
    ) -> InstagramPublishResult:
        ...


# ── Storage ──────────────────────────────────────────────────────


@dataclass
class UploadResult:
    url: str
    key: str
    size_bytes: int = 0


class StorageProvider(abc.ABC):
    @abc.abstractmethod
    async def upload_from_url(
        self, source_url: str, key: str, content_type: str = "image/jpeg"
    ) -> UploadResult:
        ...

    @abc.abstractmethod
    async def upload_bytes(
        self, data: bytes, key: str, content_type: str = "image/jpeg"
    ) -> UploadResult:
        ...

    @abc.abstractmethod
    async def get_public_url(self, key: str) -> str:
        ...
