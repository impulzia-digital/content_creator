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
def get_text_provider() -> TextProvider:
    provider = getattr(settings, "TEXT_PROVIDER", "openai")
    if provider == "openai":
        from apps.integrations.providers.openai_text import OpenAITextProvider
        return OpenAITextProvider()
    raise ValueError(f"Text provider desconocido: {provider}")


@lru_cache
def get_image_provider() -> ImageProvider:
    provider = getattr(settings, "IMAGE_PROVIDER", "openai")
    if provider == "openai":
        from apps.integrations.providers.openai_images import OpenAIImageProvider
        return OpenAIImageProvider()
    raise ValueError(f"Image provider desconocido: {provider}")


@lru_cache
def get_video_provider() -> VideoProvider:
    provider = getattr(settings, "VIDEO_PROVIDER", "creatomate")
    raise NotImplementedError(f"Video provider '{provider}' pendiente de implementar")


@lru_cache
def get_instagram_publisher() -> InstagramPublisher:
    from apps.integrations.providers.meta_instagram import MetaInstagramPublisher
    return MetaInstagramPublisher()


@lru_cache
def get_storage_provider() -> StorageProvider:
    from apps.integrations.providers.storage_s3 import S3StorageProvider
    return S3StorageProvider()
