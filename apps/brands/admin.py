from django.contrib import admin
from .models import Brand, InstagramAccount, Membership


class InstagramAccountInline(admin.TabularInline):
    model = InstagramAccount
    extra = 0
    fields = ["username", "ig_user_id", "page_id", "is_active", "token_expires_at"]
    readonly_fields = ["ig_user_id"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "industry", "is_active", "created_at"]
    list_filter = ["is_active", "industry"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [InstagramAccountInline, MembershipInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "logo_url", "description", "is_active")}),
        (
            "Identidad",
            {"fields": ("tagline", "founder_name", "industry", "target_audience", "brand_voice_prompt")},
        ),
        (
            "Tono",
            {"fields": ("tone_adjectives", "tone_description", "forbidden_words")},
        ),
        (
            "Paleta de colores",
            {"fields": ("color_primary", "color_secondary", "color_background", "color_accent", "color_text")},
        ),
        (
            "Defaults editoriales",
            {"fields": ("default_hashtags", "default_language", "preferred_image_style", "preferred_aspect_ratios")},
        ),
    )


@admin.register(InstagramAccount)
class InstagramAccountAdmin(admin.ModelAdmin):
    list_display = ["username", "brand", "is_active", "token_expires_at"]
    list_filter = ["is_active"]
    search_fields = ["username"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "brand", "role"]
    list_filter = ["role"]
    autocomplete_fields = ["user", "brand"]
