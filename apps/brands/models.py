from django.db import models
from apps.common.models import TimeStampedModel


class Brand(TimeStampedModel):
    """Marca / cliente / proyecto."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    logo_url = models.URLField(blank=True)
    description = models.TextField(blank=True)

    # Identidad de marca (del briefing Saraga)
    tagline = models.CharField(max_length=300, blank=True)
    founder_name = models.CharField(max_length=200, blank=True)
    industry = models.CharField(max_length=200, blank=True)
    target_audience = models.TextField(blank=True, help_text="Descripción del cliente ideal")
    brand_voice_prompt = models.TextField(
        blank=True,
        help_text="System prompt base inyectado en todas las generaciones de IA para esta marca",
    )

    # Tono y restricciones
    tone_adjectives = models.JSONField(
        default=list, blank=True,
        help_text="Lista de adjetivos de tono: cercano, educativo, directo...",
    )
    tone_description = models.TextField(blank=True, help_text="Descripción libre del tono")
    forbidden_words = models.JSONField(default=list, blank=True)

    # Paleta
    color_primary = models.CharField(max_length=7, blank=True, help_text="HEX #RRGGBB")
    color_secondary = models.CharField(max_length=7, blank=True)
    color_background = models.CharField(max_length=7, blank=True)
    color_accent = models.CharField(max_length=7, blank=True)
    color_text = models.CharField(max_length=7, blank=True)

    # Defaults editoriales
    default_hashtags = models.JSONField(default=list, blank=True)
    default_language = models.CharField(max_length=10, default="es")
    preferred_image_style = models.CharField(max_length=200, blank=True)
    preferred_aspect_ratios = models.JSONField(
        default=list, blank=True,
        help_text='Ej: ["4:5", "1:1", "9:16"]',
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_brand_briefing(self) -> str:
        """Retorna el briefing completo de marca para inyectar en prompts."""
        lines = [
            f"IDENTIDAD DE MARCA — {self.name}",
            "",
            "DATOS BÁSICOS",
            f"Marca: {self.name}",
            f"Tagline: {self.tagline}" if self.tagline else "",
            f"Fundador/a: {self.founder_name}" if self.founder_name else "",
            f"Industria: {self.industry}" if self.industry else "",
            f"Idioma: {self.default_language}",
            "",
            "AUDIENCIA OBJETIVO",
            self.target_audience or "No definida",
            "",
            "TONO DE VOZ",
            f"Adjetivos: {', '.join(self.tone_adjectives)}" if self.tone_adjectives else "",
            self.tone_description or "",
            f"Prohibido: {', '.join(self.forbidden_words)}" if self.forbidden_words else "",
            "",
            "PALETA DE COLORES",
            f"Principal: {self.color_primary}" if self.color_primary else "",
            f"Secundario: {self.color_secondary}" if self.color_secondary else "",
            f"Fondo: {self.color_background}" if self.color_background else "",
            f"Acento: {self.color_accent}" if self.color_accent else "",
            f"Texto: {self.color_text}" if self.color_text else "",
        ]
        return "\n".join(line for line in lines if line is not None)


class InstagramAccount(TimeStampedModel):
    """Cuenta de Instagram conectada a una marca."""

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="instagram_accounts")
    ig_user_id = models.CharField(max_length=100, help_text="Instagram User ID de la Graph API")
    username = models.CharField(max_length=100)
    access_token = models.TextField(help_text="Token cifrado en producción")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    page_id = models.CharField(max_length=100, blank=True, help_text="Facebook Page ID vinculado")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["brand", "ig_user_id"]

    def __str__(self):
        return f"@{self.username} ({self.brand.name})"


class Membership(TimeStampedModel):
    """Relación usuario ↔ marca con rol."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="memberships")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EDITOR)

    class Meta:
        unique_together = ["user", "brand"]

    def __str__(self):
        return f"{self.user.username} → {self.brand.name} ({self.role})"
