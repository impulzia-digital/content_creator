"""Tests para apps.publishing — PublishingSchedule, Publication."""

import pytest
from django.utils import timezone

from apps.publishing.models import Publication, PublishingSchedule


@pytest.mark.django_db
class TestPublishingSchedule:
    def test_create_schedule(self, variant, instagram_account):
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now() + timezone.timedelta(hours=2),
        )
        assert schedule.pk is not None
        assert schedule.status == PublishingSchedule.ScheduleStatus.QUEUED

    def test_schedule_str(self, variant, instagram_account):
        dt = timezone.now() + timezone.timedelta(hours=1)
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=dt,
        )
        s = str(schedule)
        assert str(dt.year) in s

    def test_schedule_statuses(self):
        statuses = [c[0] for c in PublishingSchedule.ScheduleStatus.choices]
        assert "queued" in statuses
        assert "publishing" in statuses
        assert "published" in statuses
        assert "failed" in statuses
        assert "cancelled" in statuses

    def test_schedule_ordering(self, variant, instagram_account):
        now = timezone.now()
        s2 = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=now + timezone.timedelta(hours=2),
        )
        s1 = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=now + timezone.timedelta(hours=1),
        )
        schedules = list(PublishingSchedule.objects.all())
        assert schedules[0] == s1  # Más próximo primero
        assert schedules[1] == s2


@pytest.mark.django_db
class TestPublication:
    def test_create_publication(self, variant, instagram_account):
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now(),
            status=PublishingSchedule.ScheduleStatus.PUBLISHED,
        )
        pub = Publication.objects.create(
            schedule=schedule,
            instagram_account=instagram_account,
            container_id="17889455560000001",
            media_id="17889455560000002",
            permalink="https://www.instagram.com/p/ABC123/",
            api_response={"id": "17889455560000002"},
            published_at=timezone.now(),
        )
        assert pub.pk is not None
        assert pub.media_id == "17889455560000002"

    def test_publication_str(self, variant, instagram_account):
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now(),
        )
        pub = Publication.objects.create(
            schedule=schedule,
            instagram_account=instagram_account,
            media_id="123456",
        )
        assert "123456" in str(pub)

    def test_publication_one_to_one(self, variant, instagram_account):
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now(),
        )
        Publication.objects.create(
            schedule=schedule,
            instagram_account=instagram_account,
        )
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Publication.objects.create(
                schedule=schedule,
                instagram_account=instagram_account,
            )

    def test_publication_defaults(self, variant, instagram_account):
        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=instagram_account,
            scheduled_for=timezone.now(),
        )
        pub = Publication.objects.create(
            schedule=schedule,
            instagram_account=instagram_account,
        )
        assert pub.container_id == ""
        assert pub.media_id == ""
        assert pub.permalink == ""
        assert pub.api_response == {}
        assert pub.error_detail == ""
        assert pub.published_at is None
