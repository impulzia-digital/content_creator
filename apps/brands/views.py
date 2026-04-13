"""Views del backoffice – Dashboard y gestión de Brands."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.brands.models import Brand, Membership
from apps.content.models import ContentBrief


@login_required
def dashboard(request):
    """Dashboard principal: métricas rápidas de la marca activa."""
    brand = request.brand
    if not brand:
        return redirect("brands:brand_list")

    briefs = ContentBrief.objects.filter(brand=brand)
    context = {
        "brand": brand,
        "total_briefs": briefs.count(),
        "draft_count": briefs.filter(status=ContentBrief.Status.DRAFT).count(),
        "generating_count": briefs.filter(status=ContentBrief.Status.GENERATING).count(),
        "review_count": briefs.filter(status=ContentBrief.Status.REVIEW).count(),
        "published_count": briefs.filter(status=ContentBrief.Status.PUBLISHED).count(),
        "failed_count": briefs.filter(status=ContentBrief.Status.FAILED).count(),
        "recent_briefs": briefs[:10],
    }
    return render(request, "brands/dashboard.html", context)


@login_required
def brand_list(request):
    """Lista de marcas del usuario."""
    memberships = Membership.objects.filter(
        user=request.user, brand__is_active=True
    ).select_related("brand")
    return render(request, "brands/brand_list.html", {"memberships": memberships})


@login_required
def brand_switch(request, slug):
    """Cambiar marca activa."""
    membership = get_object_or_404(
        Membership, user=request.user, brand__slug=slug, brand__is_active=True
    )
    request.session["active_brand_slug"] = membership.brand.slug
    return redirect("brands:dashboard")
