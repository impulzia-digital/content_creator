"""
Celery tasks para publicación en Instagram.
"""

import logging
import asyncio

from asgiref.sync import async_to_sync
from celery import shared_task
from django.utils import timezone

from apps.assets.models import Asset
from apps.content.models import ContentBrief, ContentVariant
from apps.publishing.models import Publication, PublishingSchedule

logger = logging.getLogger(__name__)


@shared_task(
    name="publishing.publish_scheduled",
    queue="publishing",
)
def publish_scheduled_task() -> dict:
    """
    Beat task: buscar schedules pendientes y publicar.
    Se ejecuta cada 5 minutos via Celery Beat.
    """
    now = timezone.now()
    pending = PublishingSchedule.objects.filter(
        status=PublishingSchedule.ScheduleStatus.QUEUED,
        scheduled_for__lte=now,
    ).select_related("variant__brief__brand", "instagram_account")[:10]

    results = []
    for schedule in pending:
        try:
            publish_single_task.delay(str(schedule.pk))
            results.append({"schedule_id": str(schedule.pk), "dispatched": True})
        except Exception as exc:
            logger.exception("Error dispatching schedule %s: %s", schedule.pk, exc)
            results.append({"schedule_id": str(schedule.pk), "error": str(exc)})

    return {"processed": len(results), "results": results}


@shared_task(
    bind=True,
    name="publishing.publish_single",
    queue="publishing",
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def publish_single_task(self, schedule_id: str) -> dict:
    """Publicar un schedule específico en Instagram."""
    from apps.integrations.registry import get_instagram_publisher

    try:
        schedule = PublishingSchedule.objects.select_related(
            "variant__brief__brand", "instagram_account"
        ).get(pk=schedule_id)
    except PublishingSchedule.DoesNotExist:
        return {"error": f"Schedule {schedule_id} no encontrado"}

    schedule.status = PublishingSchedule.ScheduleStatus.PUBLISHING
    schedule.save(update_fields=["status"])

    publisher = get_instagram_publisher()
    variant = schedule.variant
    brief = variant.brief
    account = schedule.instagram_account
    access_token = account.access_token

    try:
        result = async_to_sync(_publish_to_instagram)(
            publisher, brief, variant, account.ig_user_id, access_token
        )

        # Crear Publication
        Publication.objects.create(
            schedule=schedule,
            instagram_account=account,
            container_id=result.get("container_id", ""),
            media_id=result.get("media_id", ""),
            permalink=result.get("permalink", ""),
            api_response=result,
            published_at=timezone.now(),
        )

        schedule.status = PublishingSchedule.ScheduleStatus.PUBLISHED
        schedule.save(update_fields=["status"])

        brief.status = ContentBrief.Status.PUBLISHED
        brief.published_at = timezone.now()
        brief.save(update_fields=["status", "published_at"])

        return result

    except Exception as exc:
        logger.exception("Publish failed for schedule %s: %s", schedule_id, exc)
        schedule.status = PublishingSchedule.ScheduleStatus.FAILED
        schedule.save(update_fields=["status"])

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {"error": str(exc)}


async def _publish_to_instagram(publisher, brief, variant, ig_user_id, access_token) -> dict:
    """Lógica async de publicación según tipo de contenido."""

    caption = variant.caption
    if variant.hashtags:
        hashtag_text = " ".join(variant.hashtags[:30])
        caption = f"{caption}\n\n{hashtag_text}"

    assets = [
        asset
        async for asset in Asset.objects.filter(
            variant=variant,
            asset_type=Asset.AssetType.IMAGE,
        ).order_by("position")
    ]

    if brief.content_type == ContentBrief.ContentType.POST:
        if not assets:
            raise ValueError("No hay imagen para publicar")
        container = await publisher.create_image_container(
            ig_user_id, assets[0].file_url, caption, access_token
        )
        # Esperar a que el container esté listo
        await _wait_for_container(publisher, container.container_id, access_token)
        result = await publisher.publish_container(ig_user_id, container.container_id, access_token)
        return {"container_id": container.container_id, "media_id": result.media_id, "permalink": result.permalink}

    elif brief.content_type == ContentBrief.ContentType.CAROUSEL:
        # Crear containers hijos
        child_ids = []
        for asset in assets:
            child = await publisher.create_carousel_child_image(
                ig_user_id, asset.file_url, access_token
            )
            child_ids.append(child.container_id)

        # Crear container padre
        container = await publisher.create_carousel_container(
            ig_user_id, child_ids, caption, access_token
        )
        await _wait_for_container(publisher, container.container_id, access_token)
        result = await publisher.publish_container(ig_user_id, container.container_id, access_token)
        return {"container_id": container.container_id, "media_id": result.media_id, "permalink": result.permalink}

    elif brief.content_type == ContentBrief.ContentType.REEL:
        video_assets = [
            asset
            async for asset in Asset.objects.filter(
                variant=variant,
                asset_type=Asset.AssetType.VIDEO,
            ).order_by("position")
        ]
        if not video_assets:
            raise ValueError("No hay video para publicar como reel")

        container = await publisher.create_reel_container(
            ig_user_id, video_assets[0].file_url, caption, access_token
        )
        await _wait_for_container(publisher, container.container_id, access_token)
        result = await publisher.publish_container(ig_user_id, container.container_id, access_token)
        return {"container_id": container.container_id, "media_id": result.media_id, "permalink": result.permalink}

    else:
        raise ValueError(f"Tipo de contenido no soportado para publicación: {brief.content_type}")


async def _wait_for_container(publisher, container_id: str, access_token: str, max_checks: int = 30) -> None:
    """Esperar a que un media container esté listo (polling)."""
    import asyncio

    for _ in range(max_checks):
        status = await publisher.check_container_status(container_id, access_token)
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} falló con status ERROR")
        await asyncio.sleep(2)

    raise TimeoutError(f"Container {container_id} no estuvo listo después de {max_checks * 2}s")
