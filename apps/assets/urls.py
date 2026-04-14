from django.urls import path

from apps.assets.views import serve_asset

app_name = "assets"

urlpatterns = [
    path("media/<path:key>", serve_asset, name="serve_asset"),
]