import uuid

from django.db import models

from apps.common.models import TimeStampedModel


class PublishingSchedule(TimeStampedModel):
    """
    Programación de publicación en Instagram.
    Se crea cuando un brief es aprobado y agendado.
    """

    class ScheduleStatus(models.TextChoices):
        QUEUED = "queued", "En cola"
        PUBLISHING = "publishing", "Publicando"
        PUBLISHED = "published", "Publicado"
        FAILED = "failed", "Fallido"
        CANCELLED = "cancelled", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        "content.ContentVariant",
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    instagram_account = models.ForeignKey(
        "brands.InstagramAccount",
        on_delete=models.CASCADE,
        related_name="schedules",
    )

    scheduled_for = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=ScheduleStatus.choices,
        default=ScheduleStatus.QUEUED,
    )

    class Meta:
        ordering = ["scheduled_for"]
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
        ]

    def __str__(self):
        return f"{self.variant} → {self.scheduled_for:%Y-%m-%d %H:%M}"


class Publication(TimeStampedModel):
    """
    Registro de una publicación efectuada en Instagram.
    Trazabilidad de container_id, media_id, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.OneToOneField(
        PublishingSchedule,
        on_delete=models.CASCADE,
        related_name="publication",
    )
    instagram_account = models.ForeignKey(
        "brands.InstagramAccount",
        on_delete=models.CASCADE,
        related_name="publications",
    )

    # IDs de la Graph API
    container_id = models.CharField(max_length=100, blank=True)
    media_id = models.CharField(max_length=100, blank=True)
    permalink = models.URLField(blank=True)

    # Response crudo
    api_response = models.JSONField(default=dict, blank=True)
    error_detail = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"Publicación {self.media_id or 'pendiente'}"
