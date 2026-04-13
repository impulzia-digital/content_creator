from django.contrib import admin
from .models import ApprovalRequest


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ["variant", "decision", "requested_by", "decided_by", "decided_at", "created_at"]
    list_filter = ["decision"]
    search_fields = ["variant__brief__title", "notes"]
    readonly_fields = ["id", "variant", "requested_by"]
