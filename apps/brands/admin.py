from django import forms
from django.contrib import admin

from apps.integrations.model_catalog import get_catalog_as_choices, get_providers_for
from .models import Brand, InstagramAccount, Membership


_TEXT_PROVIDERS = [("", "— Sin override —")] + [(p, p.title()) for p in get_providers_for("text")]
_IMAGE_PROVIDERS = [("", "— Sin override —")] + [(p, p.title()) for p in get_providers_for("image")]
_VIDEO_PROVIDERS = [("", "— Sin override —")] + [
    (p, "Google Veo" if p == "veo" else p.title()) for p in get_providers_for("video")
]

_TEXT_MODEL_CHOICES = [("", "— Default del sistema —"), ("__custom__", "✏️ Personalizado…")]
_IMAGE_MODEL_CHOICES = [("", "— Default del sistema —"), ("__custom__", "✏️ Personalizado…")]
_VIDEO_MODEL_CHOICES = [("", "— Default del sistema —"), ("__custom__", "✏️ Personalizado…")]

# Pre-populate with all text models, grouped by provider
for _prov in get_providers_for("text"):
    _TEXT_MODEL_CHOICES.extend(get_catalog_as_choices(_prov, "text"))

for _prov in get_providers_for("image"):
    _IMAGE_MODEL_CHOICES.extend(get_catalog_as_choices(_prov, "image"))

for _prov in get_providers_for("video"):
    _VIDEO_MODEL_CHOICES.extend(get_catalog_as_choices(_prov, "video"))


class BrandAIDefaultsForm(forms.ModelForm):
    """Form with explicit provider/model fields that hydrate ai_provider_defaults JSON."""

    logo_url = forms.URLField(required=False, assume_scheme="https", label="Logo URL")

    ai_text_provider = forms.ChoiceField(
        choices=_TEXT_PROVIDERS, required=False, label="Provider de texto",
    )
    ai_text_model = forms.ChoiceField(
        choices=_TEXT_MODEL_CHOICES, required=False, label="Modelo de texto",
    )
    ai_text_model_custom = forms.CharField(
        required=False, label="Modelo de texto (custom)",
        help_text="Solo si elegiste 'Personalizado' arriba.",
    )
    ai_image_provider = forms.ChoiceField(
        choices=_IMAGE_PROVIDERS, required=False, label="Provider de imagen",
    )
    ai_image_model = forms.ChoiceField(
        choices=_IMAGE_MODEL_CHOICES, required=False, label="Modelo de imagen",
    )
    ai_image_model_custom = forms.CharField(
        required=False, label="Modelo de imagen (custom)",
        help_text="Solo si elegiste 'Personalizado' arriba.",
    )
    ai_video_provider = forms.ChoiceField(
        choices=_VIDEO_PROVIDERS, required=False, label="Provider de video",
    )
    ai_video_model = forms.ChoiceField(
        choices=_VIDEO_MODEL_CHOICES, required=False, label="Modelo de video",
    )
    ai_video_model_custom = forms.CharField(
        required=False, label="Modelo de video (custom)",
        help_text="Solo si elegiste 'Personalizado' arriba.",
    )

    class Meta:
        model = Brand
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            defaults = self.instance.ai_provider_defaults or {}
            text_cfg = (defaults.get("text") or {}).get("default") or {}
            image_cfg = (defaults.get("image") or {}).get("default") or {}
            video_cfg = (defaults.get("video") or {}).get("default") or {}

            self.fields["ai_text_provider"].initial = text_cfg.get("provider", "")
            text_model = text_cfg.get("model", "")
            if text_model and not any(v == text_model for v, _ in _TEXT_MODEL_CHOICES):
                self.fields["ai_text_model"].initial = "__custom__"
                self.fields["ai_text_model_custom"].initial = text_model
            else:
                self.fields["ai_text_model"].initial = text_model

            self.fields["ai_image_provider"].initial = image_cfg.get("provider", "")
            image_model = image_cfg.get("model", "")
            if image_model and not any(v == image_model for v, _ in _IMAGE_MODEL_CHOICES):
                self.fields["ai_image_model"].initial = "__custom__"
                self.fields["ai_image_model_custom"].initial = image_model
            else:
                self.fields["ai_image_model"].initial = image_model

            self.fields["ai_video_provider"].initial = video_cfg.get("provider", "")
            video_model = video_cfg.get("model", "")
            if video_model and not any(v == video_model for v, _ in _VIDEO_MODEL_CHOICES):
                self.fields["ai_video_model"].initial = "__custom__"
                self.fields["ai_video_model_custom"].initial = video_model
            else:
                self.fields["ai_video_model"].initial = video_model

    def save(self, commit=True):
        instance = super().save(commit=False)
        defaults = instance.ai_provider_defaults or {}

        # Hydrate text defaults, preserving any per-agent overrides
        text_provider = self.cleaned_data.get("ai_text_provider", "").strip()
        text_model_select = self.cleaned_data.get("ai_text_model", "").strip()
        text_model_custom = self.cleaned_data.get("ai_text_model_custom", "").strip()
        text_model = text_model_custom if text_model_select == "__custom__" else text_model_select

        text_default = {}
        if text_provider:
            text_default["provider"] = text_provider
        if text_model:
            text_default["model"] = text_model

        if text_default:
            defaults.setdefault("text", {})["default"] = text_default
        elif "text" in defaults and "default" in defaults.get("text", {}):
            defaults["text"].pop("default", None)
            if not defaults["text"]:
                del defaults["text"]

        # Hydrate image defaults, preserving any per-agent overrides
        image_provider = self.cleaned_data.get("ai_image_provider", "").strip()
        image_model_select = self.cleaned_data.get("ai_image_model", "").strip()
        image_model_custom = self.cleaned_data.get("ai_image_model_custom", "").strip()
        image_model = image_model_custom if image_model_select == "__custom__" else image_model_select

        image_default = {}
        if image_provider:
            image_default["provider"] = image_provider
        if image_model:
            image_default["model"] = image_model

        if image_default:
            defaults.setdefault("image", {})["default"] = image_default
        elif "image" in defaults and "default" in defaults.get("image", {}):
            defaults["image"].pop("default", None)
            if not defaults["image"]:
                del defaults["image"]

        # Hydrate video defaults, preserving any per-agent overrides
        video_provider = self.cleaned_data.get("ai_video_provider", "").strip()
        video_model_select = self.cleaned_data.get("ai_video_model", "").strip()
        video_model_custom = self.cleaned_data.get("ai_video_model_custom", "").strip()
        video_model = video_model_custom if video_model_select == "__custom__" else video_model_select

        video_default = {}
        if video_provider:
            video_default["provider"] = video_provider
        if video_model:
            video_default["model"] = video_model

        if video_default:
            defaults.setdefault("video", {})["default"] = video_default
        elif "video" in defaults and "default" in defaults.get("video", {}):
            defaults["video"].pop("default", None)
            if not defaults["video"]:
                del defaults["video"]

        instance.ai_provider_defaults = defaults
        if commit:
            instance.save()
        return instance


class InstagramAccountInline(admin.TabularInline):
    model = InstagramAccount
    extra = 0
    fields = ["username", "ig_user_id", "page_id", "is_active", "token_expires_at"]
    readonly_fields = ["ig_user_id"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    form = BrandAIDefaultsForm
    list_display = ["name", "slug", "industry", "is_active", "created_at"]
    list_filter = ["is_active", "industry"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [InstagramAccountInline, MembershipInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "logo_url", "description", "is_active")}),
        (
            "Identidad",
            {"fields": ("tagline", "founder_name", "industry", "target_audience", "brand_voice_prompt")},
        ),
        (
            "Tono",
            {"fields": ("tone_adjectives", "tone_description", "forbidden_words")},
        ),
        (
            "Paleta de colores",
            {"fields": ("color_primary", "color_secondary", "color_background", "color_accent", "color_text")},
        ),
        (
            "Defaults editoriales",
            {
                "fields": (
                    "default_hashtags",
                    "default_language",
                    "preferred_image_style",
                    "preferred_aspect_ratios",
                )
            },
        ),
        (
            "IA — Defaults",
            {
                "fields": (
                    "ai_text_provider",
                    "ai_text_model",
                    "ai_text_model_custom",
                    "ai_image_provider",
                    "ai_image_model",
                    "ai_image_model_custom",
                    "ai_video_provider",
                    "ai_video_model",
                    "ai_video_model_custom",
                ),
                "description": "Configura el proveedor y modelo por defecto para texto, imagen y video.",
            },
        ),
        (
            "IA — Avanzado (JSON)",
            {
                "classes": ("collapse",),
                "fields": ("ai_provider_defaults",),
                "description": "JSON completo para overrides por agente. Se actualiza automáticamente al guardar los campos de arriba.",
            },
        ),
    )


@admin.register(InstagramAccount)
class InstagramAccountAdmin(admin.ModelAdmin):
    list_display = ["username", "brand", "is_active", "token_expires_at"]
    list_filter = ["is_active"]
    search_fields = ["username"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "brand", "role"]
    list_filter = ["role"]
    autocomplete_fields = ["user", "brand"]
