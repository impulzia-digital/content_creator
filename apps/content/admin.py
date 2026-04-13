from django.contrib import admin
from .models import ContentBrief, ContentVariant, AgentRun


class ContentVariantInline(admin.TabularInline):
    model = ContentVariant
    extra = 0
    fields = ["version", "is_selected", "caption", "hashtags", "generation_cost_usd"]
    readonly_fields = ["generation_cost_usd"]


class AgentRunInline(admin.TabularInline):
    model = AgentRun
    extra = 0
    fields = ["agent_type", "status", "provider", "model_used", "duration_seconds", "cost_usd", "attempt"]
    readonly_fields = ["agent_type", "status", "provider", "model_used", "duration_seconds", "cost_usd", "attempt"]


@admin.register(ContentBrief)
class ContentBriefAdmin(admin.ModelAdmin):
    list_display = ["title", "brand", "content_type", "status", "priority", "scheduled_for", "created_at"]
    list_filter = ["status", "content_type", "brand", "priority"]
    search_fields = ["title", "raw_idea"]
    list_editable = ["status", "priority"]
    inlines = [ContentVariantInline, AgentRunInline]
    readonly_fields = ["id", "enriched_brief", "published_at"]
    fieldsets = (
        (None, {"fields": ("id", "brand", "created_by", "title", "raw_idea")}),
        ("Formato", {"fields": ("content_type", "aspect_ratio", "num_slides")}),
        ("Estado", {"fields": ("status", "error_message")}),
        ("Programación", {"fields": ("scheduled_for", "published_at")}),
        ("IA", {"fields": ("enriched_brief",)}),
        ("Meta", {"fields": ("tags", "priority")}),
    )


@admin.register(ContentVariant)
class ContentVariantAdmin(admin.ModelAdmin):
    list_display = ["brief", "version", "is_selected", "generation_cost_usd", "created_at"]
    list_filter = ["is_selected"]
    readonly_fields = ["generation_params", "generation_cost_usd"]


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ["brief", "agent_type", "status", "provider", "model_used", "duration_seconds", "cost_usd", "attempt", "created_at"]
    list_filter = ["agent_type", "status", "provider"]
    search_fields = ["brief__title"]
    readonly_fields = [
        "id", "brief", "variant", "agent_type", "status",
        "input_data", "output_data", "error_detail",
        "duration_seconds", "cost_usd", "provider", "model_used",
        "attempt", "max_attempts",
    ]
