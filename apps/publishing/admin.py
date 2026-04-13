from django.contrib import admin
from .models import PublishingSchedule, Publication


class PublicationInline(admin.StackedInline):
    model = Publication
    extra = 0
    readonly_fields = ["container_id", "media_id", "permalink", "api_response", "published_at"]


@admin.register(PublishingSchedule)
class PublishingScheduleAdmin(admin.ModelAdmin):
    list_display = ["variant", "instagram_account", "scheduled_for", "status", "created_at"]
    list_filter = ["status", "instagram_account"]
    search_fields = ["variant__brief__title"]
    inlines = [PublicationInline]


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["schedule", "instagram_account", "media_id", "permalink", "published_at"]
    search_fields = ["media_id", "permalink"]
    readonly_fields = ["container_id", "media_id", "permalink", "api_response", "error_detail"]
