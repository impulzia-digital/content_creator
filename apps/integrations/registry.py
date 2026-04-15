"""
Registry central de proveedores.

Uso:
    from apps.integrations.registry import get_text_provider, get_image_provider
    text = get_text_provider()
    result = await text.generate(request)
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from apps.integrations.base import (
    ImageProvider,
    InstagramPublisher,
    StorageProvider,
    TextProvider,
    VideoProvider,
)


@lru_cache
def get_text_provider(provider: str | None = None) -> TextProvider:
    provider = (provider or getattr(settings, "TEXT_PROVIDER", "openai")).lower()
    if provider == "openai":
        from apps.integrations.providers.openai_text import OpenAITextProvider
        return OpenAITextProvider()
    if provider == "gemini":
        from apps.integrations.providers.gemini_text import GeminiTextProvider
        return GeminiTextProvider()
    raise ValueError(f"Text provider desconocido: {provider}")


@lru_cache
def get_image_provider(provider: str | None = None) -> ImageProvider:
    provider = (provider or getattr(settings, "IMAGE_PROVIDER", "openai")).lower()
    if provider == "openai":
        from apps.integrations.providers.openai_images import OpenAIImageProvider
        return OpenAIImageProvider()
    if provider == "gemini":
        from apps.integrations.providers.gemini_images import GeminiImageProvider
        return GeminiImageProvider()
    if provider == "imagen":
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider
        return Imagen4ImageProvider()
    raise ValueError(f"Image provider desconocido: {provider}")


@lru_cache
def get_video_provider(provider: str | None = None) -> VideoProvider:
    provider = (provider or getattr(settings, "VIDEO_PROVIDER", "creatomate")).lower()
    if provider == "creatomate":
        from apps.integrations.providers.creatomate_video import CreatomateVideoProvider
        return CreatomateVideoProvider()
    if provider == "veo":
        from apps.integrations.providers.veo_video import VeoVideoProvider
        return VeoVideoProvider()
    raise ValueError(f"Video provider desconocido: {provider}")


@lru_cache
def get_instagram_publisher() -> InstagramPublisher:
    from apps.integrations.providers.meta_instagram import MetaInstagramPublisher
    return MetaInstagramPublisher()


@lru_cache
def get_storage_provider() -> StorageProvider:
    from apps.integrations.providers.storage_s3 import S3StorageProvider
    return S3StorageProvider()
