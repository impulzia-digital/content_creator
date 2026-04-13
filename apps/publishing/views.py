"""Views del backoffice – Programación y Publicaciones."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.brands.models import InstagramAccount
from apps.content.models import ContentBrief, ContentVariant
from apps.publishing.models import PublishingSchedule


@login_required
def schedule_list(request):
    """Lista de publicaciones programadas."""
    brand = request.brand
    if not brand:
        return redirect("brands:brand_list")

    schedules = PublishingSchedule.objects.filter(
        variant__brief__brand=brand,
    ).select_related("variant__brief", "instagram_account").order_by("scheduled_for")

    context = {"schedules": schedules[:50]}

    if request.htmx:
        return render(request, "publishing/partials/schedule_table.html", context)
    return render(request, "publishing/schedule_list.html", context)


@login_required
def schedule_create(request, variant_id):
    """Programar publicación de una variante."""
    variant = get_object_or_404(
        ContentVariant, pk=variant_id, brief__brand=request.brand
    )
    brand = request.brand
    accounts = InstagramAccount.objects.filter(brand=brand, is_active=True)

    if request.method == "POST":
        account_id = request.POST.get("account_id")
        scheduled_for = request.POST.get("scheduled_for")

        account = get_object_or_404(InstagramAccount, pk=account_id, brand=brand)

        schedule = PublishingSchedule.objects.create(
            variant=variant,
            instagram_account=account,
            scheduled_for=scheduled_for,
        )

        variant.brief.status = ContentBrief.Status.SCHEDULED
        variant.brief.save(update_fields=["status"])

        if request.htmx:
            return HttpResponse(
                '<span class="text-blue-600 font-bold">📅 Programado</span>'
            )
        return redirect("publishing:schedule_list")

    return render(request, "publishing/schedule_create.html", {
        "variant": variant,
        "accounts": accounts,
    })


@login_required
def schedule_cancel(request, schedule_id):
    """Cancelar una publicación programada."""
    schedule = get_object_or_404(
        PublishingSchedule,
        pk=schedule_id,
        variant__brief__brand=request.brand,
        status=PublishingSchedule.ScheduleStatus.QUEUED,
    )
    schedule.status = PublishingSchedule.ScheduleStatus.CANCELLED
    schedule.save(update_fields=["status"])

    if request.htmx:
        return HttpResponse('<span class="text-gray-500">Cancelado</span>')
    return redirect("publishing:schedule_list")
