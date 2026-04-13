"""
S3-compatible storage provider (works with AWS S3, Cloudflare R2, MinIO).
"""

from __future__ import annotations

import logging
from io import BytesIO

import boto3
import httpx
from django.conf import settings

from apps.integrations.base import StorageProvider, UploadResult

logger = logging.getLogger(__name__)


class S3StorageProvider(StorageProvider):
    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, "AWS_S3_REGION_NAME", "auto"),
        )
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
        if self._custom_domain:
            return f"https://{self._custom_domain}/{key}"
        return f"{settings.AWS_S3_ENDPOINT_URL}/{self._bucket}/{key}"
