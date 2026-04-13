from django.contrib import admin
from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "variant", "asset_type", "source", "position",
        "width", "height", "mime_type", "file_size_bytes", "created_at",
    ]
    list_filter = ["asset_type", "source", "mime_type"]
    search_fields = ["variant__brief__title", "file_key"]
    readonly_fields = [
        "id", "file_url", "file_key", "file_size_bytes",
        "generation_prompt", "generation_params",
    ]
