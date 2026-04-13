from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check: verifica DB y Redis."""
    from django.db import connection
    from django.core.cache import cache

    errors = []
    try:
        connection.ensure_connection()
    except Exception as e:
        errors.append(f"db: {e}")
    try:
        cache.set("_health", "ok", 5)
        if cache.get("_health") != "ok":
            errors.append("redis: read failed")
    except Exception as e:
        errors.append(f"redis: {e}")

    if errors:
        return JsonResponse({"status": "unhealthy", "errors": errors}, status=503)
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("", include("apps.brands.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.approvals.urls")),
    path("", include("apps.publishing.urls")),
]
