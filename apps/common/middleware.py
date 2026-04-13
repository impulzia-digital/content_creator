"""Middleware multi-brand: inyecta request.brand en cada request."""

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from apps.brands.models import Brand, Membership


class BrandMiddleware:
    """
    Resuelve la marca activa desde la sesión o la primera membresía del usuario.
    Asigna request.brand y request.membership.
    """

    EXEMPT_URLS = {"admin", "health", "accounts"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.brand = None
        request.membership = None

        # Skip para rutas exentas
        path_root = request.path.strip("/").split("/")[0] if request.path.strip("/") else ""
        if path_root in self.EXEMPT_URLS or not request.user.is_authenticated:
            return self.get_response(request)

        brand_slug = request.session.get("active_brand_slug")

        if brand_slug:
            try:
                membership = Membership.objects.select_related("brand").get(
                    user=request.user, brand__slug=brand_slug, brand__is_active=True
                )
                request.brand = membership.brand
                request.membership = membership
            except Membership.DoesNotExist:
                # Slug inválido, limpiar sesión
                request.session.pop("active_brand_slug", None)

        # Si no hay marca en sesión, buscar la primera
        if request.brand is None:
            membership = (
                Membership.objects.select_related("brand")
                .filter(user=request.user, brand__is_active=True)
                .first()
            )
            if membership:
                request.brand = membership.brand
                request.membership = membership
                request.session["active_brand_slug"] = membership.brand.slug

        return self.get_response(request)
