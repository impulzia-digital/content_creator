"""Views del backoffice – Briefs y Variantes."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.assets.models import Asset
from apps.content.models import AgentRun, ContentBrief, ContentVariant
from apps.content.tasks import generate_content_task
from apps.integrations.image_dimensions import (
    IMAGE_RESOLUTION_CHOICES,
    VALID_IMAGE_RESOLUTION_PRESETS,
    get_image_dimensions,
)
from apps.integrations.model_catalog import get_catalog_json, get_providers_for


_TEXT_PROVIDER_CHOICES = [("", "Usar defaults de la marca")] + [
    (provider, provider.title()) for provider in get_providers_for("text")
]
_IMAGE_PROVIDER_CHOICES = [("", "Usar defaults de la marca")] + [
    (provider, "Imagen (Google)" if provider == "imagen" else provider.title())
    for provider in get_providers_for("image")
]
_VIDEO_PROVIDER_CHOICES = [("", "Usar defaults de la marca")] + [
    (provider, "Google Veo" if provider == "veo" else provider.title())
    for provider in get_providers_for("video")
]

_TEXT_PROVIDER_VALUES = {value for value, _ in _TEXT_PROVIDER_CHOICES if value}
_IMAGE_PROVIDER_VALUES = {value for value, _ in _IMAGE_PROVIDER_CHOICES if value}
_VIDEO_PROVIDER_VALUES = {value for value, _ in _VIDEO_PROVIDER_CHOICES if value}


def _brief_has_required_assets(brief: ContentBrief) -> bool:
    assets = brief.variants.prefetch_related("assets").all()
    if brief.content_type == ContentBrief.ContentType.REEL:
        return any(asset.asset_type == Asset.AssetType.VIDEO for variant in assets for asset in variant.assets.all())
    if brief.content_type in (ContentBrief.ContentType.POST, ContentBrief.ContentType.STORY):
        return any(asset.asset_type == Asset.AssetType.IMAGE for variant in assets for asset in variant.assets.all())
    if brief.content_type == ContentBrief.ContentType.CAROUSEL:
        return any(asset.asset_type == Asset.AssetType.IMAGE for variant in assets for asset in variant.assets.all())
    return False


def _build_missing_output_message(brief: ContentBrief) -> str:
    if brief.content_type == ContentBrief.ContentType.REEL:
        return "Esta generación quedó sin asset de video. Puedes regenerarla con el código nuevo."
    if brief.content_type == ContentBrief.ContentType.CAROUSEL:
        return "Esta generación quedó sin assets de carrusel. Puedes regenerarla."
    return "Esta generación quedó sin assets renderizados. Puedes regenerarla."


def _build_ai_provider_overrides(request) -> dict:
    overrides: dict[str, dict] = {}

    text_provider = request.POST.get("text_provider_override", "").strip().lower()
    if text_provider and text_provider not in _TEXT_PROVIDER_VALUES:
        text_provider = ""
    text_model_select = request.POST.get("text_model_select", "").strip()
    text_model_custom = request.POST.get("text_model_custom", "").strip()
    text_model = text_model_custom if text_model_select == "__custom__" else text_model_select
    # Fallback al viejo campo por compatibilidad
    if not text_model:
        text_model = request.POST.get("text_model_override", "").strip()
    if text_provider or text_model:
        overrides.setdefault("text", {}).setdefault("default", {})
        if text_provider:
            overrides["text"]["default"]["provider"] = text_provider
        if text_model:
            overrides["text"]["default"]["model"] = text_model

    image_provider = request.POST.get("image_provider_override", "").strip().lower()
    if image_provider and image_provider not in _IMAGE_PROVIDER_VALUES:
        image_provider = ""
    image_model_select = request.POST.get("image_model_select", "").strip()
    image_model_custom = request.POST.get("image_model_custom", "").strip()
    image_model = image_model_custom if image_model_select == "__custom__" else image_model_select
    image_resolution_preset = request.POST.get("image_resolution_preset", "").strip().lower()
    if image_resolution_preset not in VALID_IMAGE_RESOLUTION_PRESETS:
        image_resolution_preset = ""
    if not image_model:
        image_model = request.POST.get("image_model_override", "").strip()
    if image_provider or image_model or image_resolution_preset:
        overrides.setdefault("image", {}).setdefault("default", {})
        if image_provider:
            overrides["image"]["default"]["provider"] = image_provider
        if image_model:
            overrides["image"]["default"]["model"] = image_model
        if image_resolution_preset:
            width, height = get_image_dimensions(
                request.POST.get("aspect_ratio", "4:5"),
                image_resolution_preset,
            )
            overrides["image"]["default"].update({
                "resolution_preset": image_resolution_preset,
                "width": width,
                "height": height,
            })

    video_provider = request.POST.get("video_provider_override", "").strip().lower()
    if video_provider and video_provider not in _VIDEO_PROVIDER_VALUES:
        video_provider = ""
    video_model_select = request.POST.get("video_model_select", "").strip()
    video_model_custom = request.POST.get("video_model_custom", "").strip()
    video_model = video_model_custom if video_model_select == "__custom__" else video_model_select
    if not video_model:
        video_model = request.POST.get("video_model_override", "").strip()
    if video_provider or video_model:
        overrides.setdefault("video", {}).setdefault("default", {})
        if video_provider:
            overrides["video"]["default"]["provider"] = video_provider
        if video_model:
            overrides["video"]["default"]["model"] = video_model

    return overrides


@login_required
def brief_list(request):
    """Lista de briefs de la marca activa."""
    brand = request.brand
    if not brand:
        return redirect("brands:brand_list")

    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")

    briefs = ContentBrief.objects.filter(brand=brand)
    if status_filter:
        briefs = briefs.filter(status=status_filter)
    if type_filter:
        briefs = briefs.filter(content_type=type_filter)

    context = {
        "briefs": briefs[:50],
        "status_choices": ContentBrief.Status.choices,
        "type_choices": ContentBrief.ContentType.choices,
        "current_status": status_filter,
        "current_type": type_filter,
    }

    if request.htmx:
        return render(request, "content/partials/brief_table.html", context)
    return render(request, "content/brief_list.html", context)


@login_required
def brief_create(request):
    """Crear un nuevo brief."""
    brand = request.brand
    if not brand:
        return redirect("brands:brand_list")

    if request.method == "POST":
        brief = ContentBrief.objects.create(
            brand=brand,
            created_by=request.user,
            title=request.POST.get("title", "").strip(),
            raw_idea=request.POST.get("raw_idea", "").strip(),
            content_type=request.POST.get("content_type", ContentBrief.ContentType.POST),
            aspect_ratio=request.POST.get("aspect_ratio", "4:5"),
            num_slides=int(request.POST.get("num_slides", 1)),
            priority=int(request.POST.get("priority", 5)),
            ai_provider_overrides=_build_ai_provider_overrides(request),
        )
        return redirect("content:brief_detail", brief_id=brief.pk)

    return render(request, "content/brief_create.html", {
        "type_choices": ContentBrief.ContentType.choices,
        "provider_choices": _IMAGE_PROVIDER_CHOICES,
        "default_text_model": settings.GEMINI_TEXT_MODEL if settings.TEXT_PROVIDER == "gemini" else settings.OPENAI_TEXT_MODEL,
        "default_image_model": (
            settings.IMAGEN_MODEL if settings.IMAGE_PROVIDER == "imagen"
            else settings.GEMINI_IMAGE_MODEL if settings.IMAGE_PROVIDER == "gemini"
            else settings.OPENAI_IMAGE_MODEL
        ),
        "default_video_model": settings.VEO_VIDEO_MODEL if settings.VIDEO_PROVIDER == "veo" else settings.CREATOMATE_VIDEO_MODEL,
        "image_resolution_choices": IMAGE_RESOLUTION_CHOICES,
        "model_catalog_json": get_catalog_json(),
        "text_provider_choices": _TEXT_PROVIDER_CHOICES,
        "image_provider_choices": _IMAGE_PROVIDER_CHOICES,
        "video_provider_choices": _VIDEO_PROVIDER_CHOICES,
    })


@login_required
def brief_detail(request, brief_id):
    """Detalle de un brief con sus variantes y ejecuciones."""
    brief = get_object_or_404(ContentBrief, pk=brief_id, brand=request.brand)
    variants = brief.variants.prefetch_related("assets", "approval_requests").all()
    has_required_assets = _brief_has_required_assets(brief)
    generation_incomplete = brief.status in {
        ContentBrief.Status.REVIEW,
        ContentBrief.Status.APPROVED,
        ContentBrief.Status.SCHEDULED,
    } and not has_required_assets

    # Mostrar solo las ejecuciones de la última generación exitosa
    latest_enricher = brief.agent_runs.filter(
        agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
        status=AgentRun.RunStatus.SUCCESS,
    ).first()  # ya ordena por -created_at

    if latest_enricher:
        runs = brief.agent_runs.filter(created_at__gte=latest_enricher.created_at)
    else:
        runs = brief.agent_runs.all()[:20]

    context = {
        "brief": brief,
        "variants": variants,
        "runs": runs,
        "can_generate": brief.status in (ContentBrief.Status.DRAFT, ContentBrief.Status.FAILED) or generation_incomplete,
        "generation_incomplete": generation_incomplete,
        "missing_output_message": _build_missing_output_message(brief) if generation_incomplete else "",
    }
    return render(request, "content/brief_detail.html", context)


@login_required
def brief_generate(request, brief_id):
    """Disparar generación de contenido via Celery."""
    brief = get_object_or_404(ContentBrief, pk=brief_id, brand=request.brand)
    generation_incomplete = not _brief_has_required_assets(brief)

    if brief.status not in (ContentBrief.Status.DRAFT, ContentBrief.Status.FAILED) and not generation_incomplete:
        if request.htmx:
            return HttpResponse(
                '<span class="text-red-500">El brief no está en estado válido para generar.</span>',
                status=400,
            )
        return redirect("content:brief_detail", brief_id=brief.pk)

    brief.status = ContentBrief.Status.GENERATING
    brief.error_message = ""
    brief.save(update_fields=["status", "error_message"])
    generate_content_task.delay(str(brief.pk))

    if request.htmx:
        return HttpResponse(
            '<span class="text-yellow-500 font-bold">⏳ Generando...</span>'
        )
    return redirect("content:brief_detail", brief_id=brief.pk)


@login_required
def variant_select(request, variant_id):
    """Marcar variante como seleccionada."""
    variant = get_object_or_404(
        ContentVariant, pk=variant_id, brief__brand=request.brand
    )
    # Deseleccionar todas las demás del mismo brief
    ContentVariant.objects.filter(brief=variant.brief).update(is_selected=False)
    variant.is_selected = True
    variant.save(update_fields=["is_selected"])

    if request.htmx:
        return HttpResponse('<span class="text-green-600 font-bold">✓ Seleccionada</span>')
    return redirect("content:brief_detail", brief_id=variant.brief.pk)
