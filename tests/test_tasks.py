"""Tests para Celery tasks — generate_content_task y publish_* tasks."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from django.utils import timezone

from apps.content.models import ContentBrief, ContentVariant
from apps.content.tasks import generate_content_task
from apps.publishing.models import PublishingSchedule, Publication
from apps.publishing.tasks import (
    _publish_to_instagram,
    _wait_for_container,
    publish_scheduled_task,
    publish_single_task,
)
from apps.assets.models import Asset
from apps.integrations.base import InstagramMediaContainer, InstagramPublishResult

pytestmark = pytest.mark.django_db(transaction=True)


# ── generate_content_task ─────────────────────────────────────


class TestGenerateContentTask:
    def test_brief_not_found_returns_error(self):
        result = generate_content_task.apply(
            args=["00000000-0000-0000-0000-000000000000"]
        ).get()
        assert "error" in result
        assert "no encontrado" in result["error"]

    @patch("apps.agents.orchestrator.ContentOrchestrator")
    def test_success_returns_result(self, MockOrch, brief):
        mock_instance = MockOrch.return_value
        mock_instance.generate_content = AsyncMock(
            return_value={"success": True, "total_cost_usd": 0.05}
        )

        result = generate_content_task.apply(args=[str(brief.pk)]).get()

        assert result["success"] is True
        assert result["total_cost_usd"] == 0.05
        mock_instance.generate_content.assert_called_once()


# ── publish_scheduled_task ────────────────────────────────────


class TestPublishScheduledTask:
    def test_no_pending_schedules(self):
        result = publish_scheduled_task.apply().get()
        assert result["processed"] == 0
        assert result["results"] == []

    @patch("apps.publishing.tasks.publish_single_task")
    def test_dispatches_due_schedules(
        self, mock_publish, brief, brand, variant, instagram_account
    ):
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now() - timezone.timedelta(minutes=5),
            status=PublishingSchedule.ScheduleStatus.QUEUED,
        )

        mock_publish.delay = MagicMock()
        result = publish_scheduled_task.apply().get()

        assert result["processed"] == 1
        mock_publish.delay.assert_called_once_with(str(schedule.pk))

    def test_ignores_future_schedules(self, brief, brand, variant, instagram_account):
        PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now() + timezone.timedelta(hours=2),
            status=PublishingSchedule.ScheduleStatus.QUEUED,
        )

        result = publish_scheduled_task.apply().get()
        assert result["processed"] == 0


# ── _publish_to_instagram (async logic) ──────────────────────


class TestPublishToInstagramLogic:
    @pytest.mark.asyncio
    async def test_post_publish_flow(self, brief, brand, variant, instagram_account):
        await Asset.objects.acreate(
            variant=variant,
            asset_type=Asset.AssetType.IMAGE,
            file_url="https://cdn.example.com/image.jpg",
            file_key="brands/test/content/post.jpg",
            position=0,
        )
        variant.caption = "Test caption"
        variant.hashtags = ["#test", "#python"]
        await variant.asave()

        mock_publisher = AsyncMock()
        mock_publisher.create_image_container.return_value = InstagramMediaContainer(
            container_id="C123"
        )
        mock_publisher.check_container_status.return_value = "FINISHED"
        mock_publisher.publish_container.return_value = InstagramPublishResult(
            media_id="M456", permalink="https://instagram.com/p/abc"
        )

        with patch(
            "apps.integrations.providers.storage_s3.build_presigned_storage_url",
            return_value="https://signed.example.com/post.jpg?sig=1",
        ):
            result = await _publish_to_instagram(
                mock_publisher, brief, variant,
                instagram_account.ig_user_id,
                instagram_account.access_token,
            )

        assert result["container_id"] == "C123"
        assert result["media_id"] == "M456"
        assert "instagram.com" in result["permalink"]
        assert mock_publisher.create_image_container.await_args.args[1] == "https://signed.example.com/post.jpg?sig=1"

    @pytest.mark.asyncio
    async def test_carousel_publish_flow(
        self, carousel_brief, brand, instagram_account
    ):
        variant = await ContentVariant.objects.acreate(
            brief=carousel_brief, version=1
        )
        variant.caption = "Carousel post"
        variant.hashtags = []
        await variant.asave()

        for i in range(3):
            await Asset.objects.acreate(
                variant=variant,
                asset_type=Asset.AssetType.IMAGE,
                file_url=f"https://cdn.example.com/slide_{i}.jpg",
                file_key=f"brands/test/content/slide_{i}.jpg",
                position=i,
            )

        mock_publisher = AsyncMock()
        mock_publisher.create_carousel_child_image.return_value = InstagramMediaContainer(
            container_id="CHILD"
        )
        mock_publisher.create_carousel_container.return_value = InstagramMediaContainer(
            container_id="PARENT"
        )
        mock_publisher.check_container_status.return_value = "FINISHED"
        mock_publisher.publish_container.return_value = InstagramPublishResult(
            media_id="M789", permalink="https://instagram.com/p/carousel"
        )

        with patch(
            "apps.integrations.providers.storage_s3.build_presigned_storage_url",
            side_effect=[
                "https://signed.example.com/slide_0.jpg?sig=1",
                "https://signed.example.com/slide_1.jpg?sig=1",
                "https://signed.example.com/slide_2.jpg?sig=1",
            ],
        ):
            result = await _publish_to_instagram(
                mock_publisher, carousel_brief, variant,
                instagram_account.ig_user_id,
                instagram_account.access_token,
            )

        assert result["media_id"] == "M789"
        assert mock_publisher.create_carousel_child_image.call_count == 3
        assert mock_publisher.create_carousel_child_image.await_args_list[0].args[1] == "https://signed.example.com/slide_0.jpg?sig=1"

    @pytest.mark.asyncio
    async def test_post_without_image_raises(self, brief, brand, variant, instagram_account):
        variant.caption = "No image"
        await variant.asave()

        mock_publisher = AsyncMock()
        with pytest.raises(ValueError, match="No hay imagen"):
            await _publish_to_instagram(
                mock_publisher, brief, variant,
                instagram_account.ig_user_id,
                instagram_account.access_token,
            )

    @pytest.mark.asyncio
    async def test_reel_publish_flow(self, reel_brief, brand, instagram_account):
        variant = await ContentVariant.objects.acreate(brief=reel_brief, version=1)
        variant.caption = "Reel caption"
        variant.hashtags = []
        await variant.asave()

        await Asset.objects.acreate(
            variant=variant,
            asset_type=Asset.AssetType.VIDEO,
            file_url="https://cdn.example.com/video.mp4",
            file_key="brands/test/content/reel.mp4",
            position=0,
        )

        mock_publisher = AsyncMock()
        mock_publisher.create_reel_container.return_value = InstagramMediaContainer(
            container_id="REEL_C"
        )
        mock_publisher.check_container_status.return_value = "FINISHED"
        mock_publisher.publish_container.return_value = InstagramPublishResult(
            media_id="REEL_M", permalink="https://instagram.com/reel/xyz"
        )

        with patch(
            "apps.integrations.providers.storage_s3.build_presigned_storage_url",
            return_value="https://signed.example.com/reel.mp4?sig=1",
        ):
            result = await _publish_to_instagram(
                mock_publisher, reel_brief, variant,
                instagram_account.ig_user_id,
                instagram_account.access_token,
            )

        assert result["container_id"] == "REEL_C"
        assert result["media_id"] == "REEL_M"
        assert mock_publisher.create_reel_container.await_args.args[1] == "https://signed.example.com/reel.mp4?sig=1"


# ── _wait_for_container ──────────────────────────────────────


@pytest.mark.asyncio
class TestWaitForContainer:
    async def test_immediate_finished(self):
        publisher = AsyncMock()
        publisher.check_container_status.return_value = "FINISHED"
        await _wait_for_container(publisher, "C1", "token", max_checks=3)
        publisher.check_container_status.assert_called_once()

    async def test_error_raises(self):
        publisher = AsyncMock()
        publisher.check_container_status.return_value = "ERROR"
        with pytest.raises(RuntimeError, match="ERROR"):
            await _wait_for_container(publisher, "C1", "token", max_checks=3)

    async def test_retry_then_finished(self):
        publisher = AsyncMock()
        publisher.check_container_status.side_effect = [
            "IN_PROGRESS", "IN_PROGRESS", "FINISHED"
        ]
        with patch("apps.publishing.tasks.asyncio.sleep", new_callable=AsyncMock):
            await _wait_for_container(publisher, "C1", "token", max_checks=5)
        assert publisher.check_container_status.call_count == 3
