import uuid
from decimal import Decimal

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
    seed_key = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Clave estable para sincronizar briefs versionados desde seed data",
    )
    raw_idea = models.TextField(
        help_text="Idea cruda tal como la escribe el usuario o viene del spreadsheet"
    )
    enriched_brief = models.JSONField(
        null=True,
        blank=True,
        help_text="Brief expandido por BriefEnricherAgent (JSON estructurado)",
    )
    ai_provider_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Overrides opcionales para este brief. Soporta nivel default o por agente. Ej: "
            '{"text": {"default": {"provider": "gemini", "model": "gemini-2.5-pro"}}, '
            '"image": {"default": {"provider": "gemini", "model": "gemini-3-pro-image-preview"}}}'
        ),
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
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "seed_key"],
                condition=models.Q(seed_key__isnull=False) & ~models.Q(seed_key=""),
                name="content_brief_seed_key_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["brand", "status"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["content_type"]),
        ]

    @property
    def latest_generation_cost_usd(self):
        """Costo de la última generación exitosa visible para el usuario."""
        latest_enricher = self.agent_runs.filter(
            agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            status=AgentRun.RunStatus.SUCCESS,
        ).first()
        if not latest_enricher:
            return Decimal("0")

        total = self.agent_runs.filter(
            created_at__gte=latest_enricher.created_at,
            status=AgentRun.RunStatus.SUCCESS,
        ).aggregate(total=models.Sum("cost_usd"))["total"]
        return total or Decimal("0")

    @property
    def total_cost_usd(self):
        """Costo actual del brief, alineado con la última generación mostrada."""
        selected_variant = self.variants.filter(is_selected=True).first()
        if selected_variant and selected_variant.generation_cost_usd:
            return selected_variant.generation_cost_usd

        latest_variant = self.variants.order_by("-version", "-created_at").first()
        if latest_variant and latest_variant.generation_cost_usd:
            return latest_variant.generation_cost_usd

        return self.latest_generation_cost_usd

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

    @property
    def display_generation_cost_usd(self):
        """Costo mostrado en UI con fallback para variantes históricas sin backfill."""
        if self.generation_cost_usd:
            return self.generation_cost_usd

        if self.is_selected:
            return self.brief.total_cost_usd

        total = self.agent_runs.filter(
            status=AgentRun.RunStatus.SUCCESS,
        ).aggregate(total=models.Sum("cost_usd"))["total"]
        return total or Decimal("0")

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
