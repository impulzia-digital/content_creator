"""Tests para apps.common — TimeStampedModel, BrandScopedManager, AuditEvent."""

import pytest
from django.contrib.auth.models import User

from apps.common.models import AuditEvent, BrandScopedManager


# ── AuditEvent ────────────────────────────────────────────────


@pytest.mark.django_db
class TestAuditEvent:
    def test_create_audit_event(self, user, brand):
        event = AuditEvent.objects.create(
            actor=user,
            brand=brand,
            action="content.created",
            target_type="ContentBrief",
            target_id="abc-123",
            metadata={"source": "backoffice"},
            ip_address="192.168.1.1",
        )
        assert event.pk is not None
        assert event.action == "content.created"
        assert event.metadata == {"source": "backoffice"}

    def test_audit_event_uuid_pk(self, user):
        event = AuditEvent.objects.create(actor=user, action="test.action")
        assert len(str(event.pk)) == 36  # UUID format

    def test_audit_event_str(self, user):
        event = AuditEvent.objects.create(actor=user, action="test.login")
        assert "test.login" in str(event)
        assert user.username in str(event)

    def test_audit_event_nullable_fields(self, db):
        event = AuditEvent.objects.create(action="system.boot")
        assert event.actor is None
        assert event.brand is None
        assert event.ip_address is None

    def test_audit_event_ordering(self, user):
        e1 = AuditEvent.objects.create(actor=user, action="first")
        e2 = AuditEvent.objects.create(actor=user, action="second")
        events = list(AuditEvent.objects.all())
        assert events[0] == e2  # Más reciente primero
        assert events[1] == e1

    def test_audit_event_metadata_default(self, user):
        event = AuditEvent.objects.create(actor=user, action="test")
        assert event.metadata == {}


# ── BrandScopedManager ───────────────────────────────────────


@pytest.mark.django_db
class TestBrandScopedManager:
    def test_for_brand_filters_correctly(self, brand, user):
        from apps.content.models import ContentBrief

        ContentBrief.objects.create(
            brand=brand, title="Mine", raw_idea="test", created_by=user
        )
        from apps.brands.models import Brand

        other = Brand.objects.create(name="Other", slug="other")
        ContentBrief.objects.create(
            brand=other, title="Not mine", raw_idea="test2", created_by=user
        )

        mine = ContentBrief.objects.for_brand(brand)
        assert mine.count() == 1
        assert mine.first().title == "Mine"
