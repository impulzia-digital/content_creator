import uuid

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, next_creation_order


class ApprovalRequest(TimeStampedModel):
    """
    Solicitud de aprobación para una variante de contenido.
    Un brief puede tener múltiples rondas de aprobación.
    """

    class Decision(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"
        CHANGES_REQUESTED = "changes_requested", "Cambios solicitados"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_order = models.BigIntegerField(default=next_creation_order, editable=False, db_index=True)
    variant = models.ForeignKey(
        "content.ContentVariant",
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approval_requests_created",
    )

    decision = models.CharField(
        max_length=20, choices=Decision.choices, default=Decision.PENDING
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Feedback del aprobador")

    class Meta:
        ordering = ["-created_at", "-created_order"]

    def __str__(self):
        return f"Aprobación {self.get_decision_display()} — {self.variant}"
