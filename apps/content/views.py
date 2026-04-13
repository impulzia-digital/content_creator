"""Views del backoffice – Briefs y Variantes."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.content.models import AgentRun, ContentBrief, ContentVariant
from apps.content.tasks import generate_content_task


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
        )
        return redirect("content:brief_detail", brief_id=brief.pk)

    return render(request, "content/brief_create.html", {
        "type_choices": ContentBrief.ContentType.choices,
    })


@login_required
def brief_detail(request, brief_id):
    """Detalle de un brief con sus variantes y ejecuciones."""
    brief = get_object_or_404(ContentBrief, pk=brief_id, brand=request.brand)
    variants = brief.variants.prefetch_related("assets", "approval_requests").all()
    runs = brief.agent_runs.all()[:20]

    context = {
        "brief": brief,
        "variants": variants,
        "runs": runs,
    }
    return render(request, "content/brief_detail.html", context)


@login_required
def brief_generate(request, brief_id):
    """Disparar generación de contenido via Celery."""
    brief = get_object_or_404(ContentBrief, pk=brief_id, brand=request.brand)

    if brief.status not in (ContentBrief.Status.DRAFT, ContentBrief.Status.FAILED):
        if request.htmx:
            return HttpResponse(
                '<span class="text-red-500">El brief no está en estado válido para generar.</span>',
                status=400,
            )
        return redirect("content:brief_detail", brief_id=brief.pk)

    brief.status = ContentBrief.Status.GENERATING
    brief.save(update_fields=["status"])
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
