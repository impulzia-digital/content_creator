from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["action", "actor", "brand", "target_type", "target_id", "created_at"]
    list_filter = ["action", "brand", "created_at"]
    search_fields = ["action", "target_type", "target_id"]
    readonly_fields = [
        "id", "actor", "brand", "action", "target_type",
        "target_id", "metadata", "ip_address", "created_at",
    ]
    date_hierarchy = "created_at"
