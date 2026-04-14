"""
S3-compatible storage provider (works with AWS S3, Cloudflare R2, MinIO).
"""

from __future__ import annotations

import logging
from io import BytesIO
from urllib.parse import quote

import boto3
import httpx
from django.conf import settings

from apps.integrations.base import StorageProvider, UploadResult

logger = logging.getLogger(__name__)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "AWS_S3_REGION_NAME", "auto"),
    )


def build_public_storage_url(key: str) -> str:
    normalized_key = key.lstrip("/")
    quoted_key = quote(normalized_key, safe="/")

    custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "").strip().rstrip("/")
    if custom_domain:
        return f"https://{custom_domain}/{quoted_key}"

    public_media_base_url = getattr(settings, "PUBLIC_MEDIA_BASE_URL", "").strip().rstrip("/")
    if public_media_base_url:
        return f"{public_media_base_url}/assets/media/{quoted_key}"

    return f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_STORAGE_BUCKET_NAME}/{quoted_key}"


def build_presigned_storage_url(key: str, expires_in: int = 3600) -> str:
    normalized_key = key.lstrip("/")
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": normalized_key,
        },
        ExpiresIn=expires_in,
    )


class S3StorageProvider(StorageProvider):
    def __init__(self):
        self._client = get_s3_client()
        self._bucket = settings.AWS_STORAGE_BUCKET_NAME
        self._custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "")

    async def upload_from_url(
        self, source_url: str, key: str, content_type: str = "image/jpeg"
    ) -> UploadResult:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(source_url)
            resp.raise_for_status()
            data = resp.content

        return await self.upload_bytes(data, key, content_type)

    async def upload_bytes(
        self, data: bytes, key: str, content_type: str = "image/jpeg"
    ) -> UploadResult:
        self._client.upload_fileobj(
            BytesIO(data),
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ACL": "public-read"},
        )
        url = await self.get_public_url(key)
        return UploadResult(url=url, key=key, size_bytes=len(data))

    async def get_public_url(self, key: str) -> str:
        return build_public_storage_url(key)
