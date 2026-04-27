import uuid
from django.db import models


def next_creation_order() -> int:
    """Monotonic-ish timestamp from UUID1 for deterministic tie-breaking."""
    return uuid.uuid1().time


class TimeStampedModel(models.Model):
    """Abstract base con created_at / updated_at."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BrandScopedManager(models.Manager):
    """Manager que filtra por brand."""

    def for_brand(self, brand):
        return self.filter(brand=brand)


class AuditEvent(models.Model):
    """Registro inmutable de toda acción relevante del sistema."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    brand = models.ForeignKey(
        "brands.Brand", null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["brand", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor} @ {self.created_at:%Y-%m-%d %H:%M}"
