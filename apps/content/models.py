import uuid

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, BrandScopedManager


class ContentBrief(TimeStampedModel):
    """
    Brief editorial: la unidad de planificación.
    Desde aquí se disparan los sub-agentes.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ENRICHING = "enriching", "Enriqueciendo brief"
        READY = "ready", "Listo para generar"
        GENERATING = "generating", "Generando contenido"
        REVIEW = "review", "En revisión"
        APPROVED = "approved", "Aprobado"
        SCHEDULED = "scheduled", "Programado"
        PUBLISHED = "published", "Publicado"
        FAILED = "failed", "Fallido"
        ARCHIVED = "archived", "Archivado"

    class ContentType(models.TextChoices):
        POST = "post", "Post (imagen)"
        CAROUSEL = "carousel", "Carrusel"
        REEL = "reel", "Reel (video)"
        STORY = "story", "Story"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(
        "brands.Brand", on_delete=models.CASCADE, related_name="briefs"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_briefs",
    )

    # Brief input
    title = models.CharField(max_length=300)
    raw_idea = models.TextField(
        help_text="Idea cruda tal como la escribe el usuario o viene del spreadsheet"
    )
    enriched_brief = models.JSONField(
        null=True,
        blank=True,
        help_text="Brief expandido por BriefEnricherAgent (JSON estructurado)",
    )

    # Tipo y formato
    content_type = models.CharField(
        max_length=20, choices=ContentType.choices, default=ContentType.POST
    )
    aspect_ratio = models.CharField(max_length=10, default="4:5")
    num_slides = models.PositiveSmallIntegerField(
        default=1, help_text="1 para post/reel/story, 2-10 para carrusel"
    )

    # Estado
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    error_message = models.TextField(blank=True)

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    tags = models.JSONField(default=list, blank=True)
    priority = models.PositiveSmallIntegerField(default=5, help_text="1=Urgente, 10=Baja")

    objects = BrandScopedManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["brand", "status"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["content_type"]),
        ]

    def __str__(self):
        return f"[{self.get_content_type_display()}] {self.title}"


class ContentVariant(TimeStampedModel):
    """
    Variante generada por los sub-agentes.
    Cada brief puede tener N variantes (A/B testing, iteraciones).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brief = models.ForeignKey(
        ContentBrief, on_delete=models.CASCADE, related_name="variants"
    )
    version = models.PositiveSmallIntegerField(default=1)
    is_selected = models.BooleanField(
        default=False, help_text="Variante seleccionada para publicar"
    )

    # Copy generado
    caption = models.TextField(blank=True)
    hashtags = models.JSONField(default=list, blank=True)
    alt_text = models.CharField(max_length=1000, blank=True)

    # Metadata de generación
    generation_params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Parámetros usados: model, temperature, prompts, seeds...",
    )
    generation_cost_usd = models.DecimalField(
        max_digits=8, decimal_places=4, default=0
    )

    class Meta:
        ordering = ["brief", "version"]
        unique_together = ["brief", "version"]

    def __str__(self):
        return f"{self.brief.title} — v{self.version}"


class AgentRun(TimeStampedModel):
    """
    Registro de ejecución de un sub-agente sobre un brief/variante.
    Trazabilidad completa de qué agente hizo qué, cuándo y con qué resultado.
    """

    class AgentType(models.TextChoices):
        BRIEF_ENRICHER = "brief_enricher", "Brief Enricher"
        COPY = "copy", "Copy Agent"
        IMAGE = "image", "Image Agent"
        CAROUSEL = "carousel", "Carousel Agent"
        VIDEO = "video", "Video Agent"
        HASHTAG = "hashtag", "Hashtag Agent"

    class RunStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        RUNNING = "running", "Ejecutando"
        SUCCESS = "success", "Exitoso"
        FAILED = "failed", "Fallido"
        RETRYING = "retrying", "Reintentando"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brief = models.ForeignKey(
        ContentBrief, on_delete=models.CASCADE, related_name="agent_runs"
    )
    variant = models.ForeignKey(
        ContentVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_runs",
    )
    agent_type = models.CharField(max_length=20, choices=AgentType.choices)
    status = models.CharField(
        max_length=20, choices=RunStatus.choices, default=RunStatus.PENDING
    )

    # I/O
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict, blank=True)
    error_detail = models.TextField(blank=True)

    # Costos y timing
    duration_seconds = models.FloatField(null=True, blank=True)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    provider = models.CharField(max_length=50, blank=True, help_text="openai, fal, creatomate...")
    model_used = models.CharField(max_length=100, blank=True)

    # Retries
    attempt = models.PositiveSmallIntegerField(default=1)
    max_attempts = models.PositiveSmallIntegerField(default=3)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["brief", "agent_type"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.get_agent_type_display()} → {self.brief.title} [{self.status}]"
