import uuid

from django.db import models

from apps.common.models import TimeStampedModel


class Asset(TimeStampedModel):
    """
    Archivo multimedia generado o subido.
    Conectado a una variante de contenido.
    """

    class AssetType(models.TextChoices):
        IMAGE = "image", "Imagen"
        VIDEO = "video", "Video"
        THUMBNAIL = "thumbnail", "Thumbnail"
        AUDIO = "audio", "Audio"

    class Source(models.TextChoices):
        GENERATED = "generated", "Generado por IA"
        UPLOADED = "uploaded", "Subido manualmente"
        TEMPLATE = "template", "Renderizado de template"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        "content.ContentVariant",
        on_delete=models.CASCADE,
        related_name="assets",
    )
    asset_type = models.CharField(max_length=20, choices=AssetType.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.GENERATED)

    # Archivo
    file_url = models.URLField(help_text="URL en S3/R2")
    file_key = models.CharField(max_length=500, help_text="Key en el bucket")
    file_size_bytes = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, default="image/jpeg")
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True, help_text="Solo para video/audio")

    # Orden (para carruseles)
    position = models.PositiveSmallIntegerField(
        default=0, help_text="Orden dentro del carrusel (0-indexed)"
    )

    # Prompt de generación (trazabilidad)
    generation_prompt = models.TextField(blank=True)
    generation_params = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["variant", "position"]

    def __str__(self):
        return f"{self.get_asset_type_display()} #{self.position} — {self.variant}"
