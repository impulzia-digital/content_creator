"""
Meta Graph API — Instagram Content Publishing.

Ref: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing
"""

from __future__ import annotations

import logging

import httpx

from apps.integrations.base import (
    InstagramMediaContainer,
    InstagramPublisher,
    InstagramPublishResult,
)

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class MetaInstagramPublisher(InstagramPublisher):
    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    async def create_image_container(
        self, ig_user_id: str, image_url: str, caption: str, access_token: str
    ) -> InstagramMediaContainer:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{BASE_URL}/{ig_user_id}/media",
                headers=self._headers(access_token),
                data={
                    "image_url": image_url,
                    "caption": caption,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return InstagramMediaContainer(container_id=data["id"])

    async def create_carousel_container(
        self,
        ig_user_id: str,
        children_container_ids: list[str],
        caption: str,
        access_token: str,
    ) -> InstagramMediaContainer:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Primero crear containers hijos (ya deben existir)
            # Luego crear el padre
            resp = await client.post(
                f"{BASE_URL}/{ig_user_id}/media",
                headers=self._headers(access_token),
                data={
                    "media_type": "CAROUSEL",
                    "children": ",".join(children_container_ids),
                    "caption": caption,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return InstagramMediaContainer(container_id=data["id"])

    async def create_reel_container(
        self,
        ig_user_id: str,
        video_url: str,
        caption: str,
        access_token: str,
        thumb_offset_ms: int = 0,
    ) -> InstagramMediaContainer:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            payload: dict = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
            }
            if thumb_offset_ms:
                payload["thumb_offset"] = str(thumb_offset_ms)

            resp = await client.post(
                f"{BASE_URL}/{ig_user_id}/media",
                headers=self._headers(access_token),
                data=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return InstagramMediaContainer(container_id=data["id"])

    async def create_carousel_child_image(
        self, ig_user_id: str, image_url: str, access_token: str
    ) -> InstagramMediaContainer:
        """Crea un container hijo de imagen para carrusel (sin caption)."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{BASE_URL}/{ig_user_id}/media",
                headers=self._headers(access_token),
                data={
                    "image_url": image_url,
                    "is_carousel_item": "true",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return InstagramMediaContainer(container_id=data["id"])

    async def check_container_status(
        self, container_id: str, access_token: str
    ) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{BASE_URL}/{container_id}",
                headers=self._headers(access_token),
                params={"fields": "status_code"},
            )
            resp.raise_for_status()
            return resp.json().get("status_code", "UNKNOWN")

    async def publish_container(
        self, ig_user_id: str, container_id: str, access_token: str
    ) -> InstagramPublishResult:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{BASE_URL}/{ig_user_id}/media_publish",
                headers=self._headers(access_token),
                data={"creation_id": container_id},
            )
            resp.raise_for_status()
            data = resp.json()
            media_id = data.get("id", "")

            # Obtener permalink
            permalink = ""
            if media_id:
                detail = await client.get(
                    f"{BASE_URL}/{media_id}",
                    headers=self._headers(access_token),
                    params={"fields": "permalink"},
                )
                if detail.status_code == 200:
                    permalink = detail.json().get("permalink", "")

            return InstagramPublishResult(
                media_id=media_id,
                permalink=permalink,
                raw_response=data,
            )
