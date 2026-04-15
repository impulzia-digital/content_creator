"""Tests para apps.brands — Brand, InstagramAccount, Membership."""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from apps.brands.models import Brand, InstagramAccount, Membership


@pytest.mark.django_db
class TestBrand:
    def test_create_brand(self, brand):
        assert brand.pk is not None
        assert brand.name == "Test Brand"
        assert brand.slug == "test-brand"
        assert brand.is_active is True

    def test_brand_str(self, brand):
        assert str(brand) == "Test Brand"

    def test_brand_slug_unique(self, brand):
        with pytest.raises(IntegrityError):
            Brand.objects.create(name="Duplicate", slug="test-brand")

    def test_brand_ordering(self, db):
        b1 = Brand.objects.create(name="Zebra", slug="zebra")
        b2 = Brand.objects.create(name="Alpha", slug="alpha")
        brands = list(Brand.objects.all())
        assert brands[0] == b2  # Alphabetical
        assert brands[1] == b1

    def test_brand_json_fields_defaults(self, db):
        b = Brand.objects.create(name="Minimal", slug="minimal")
        assert b.tone_adjectives == []
        assert b.forbidden_words == []
        assert b.default_hashtags == []
        assert b.preferred_aspect_ratios == []
        assert b.ai_provider_defaults == {}

    def test_brand_get_brand_briefing(self, brand):
        briefing = brand.get_brand_briefing()
        assert "Test Brand" in briefing
        assert "Technology" in briefing
        assert "#2563EB" in briefing
        assert "Developers and testers" in briefing

    def test_brand_briefing_minimal(self, db):
        b = Brand.objects.create(name="Simple", slug="simple")
        briefing = b.get_brand_briefing()
        assert "Simple" in briefing
        assert "IDENTIDAD DE MARCA" in briefing

    def test_brand_timestamps(self, brand):
        assert brand.created_at is not None
        assert brand.updated_at is not None


@pytest.mark.django_db
class TestInstagramAccount:
    def test_create_account(self, instagram_account, brand):
        assert instagram_account.brand == brand
        assert instagram_account.username == "testbrand_ig"
        assert instagram_account.is_active is True

    def test_account_str(self, instagram_account):
        assert "@testbrand_ig" in str(instagram_account)
        assert "Test Brand" in str(instagram_account)

    def test_account_unique_per_brand(self, brand, instagram_account):
        with pytest.raises(IntegrityError):
            InstagramAccount.objects.create(
                brand=brand,
                ig_user_id="17841400000000001",  # mismo ID
                username="duplicate",
                access_token="token",
            )

    def test_multiple_accounts_per_brand(self, brand):
        InstagramAccount.objects.create(
            brand=brand, ig_user_id="111", username="acc1", access_token="t1"
        )
        InstagramAccount.objects.create(
            brand=brand, ig_user_id="222", username="acc2", access_token="t2"
        )
        assert brand.instagram_accounts.count() == 2


@pytest.mark.django_db
class TestMembership:
    def test_create_membership(self, membership, user, brand):
        assert membership.user == user
        assert membership.brand == brand
        assert membership.role == Membership.Role.EDITOR

    def test_membership_str(self, membership):
        s = str(membership)
        assert "testuser" in s
        assert "Test Brand" in s
        assert "editor" in s

    def test_membership_unique_user_brand(self, user, brand, membership):
        with pytest.raises(IntegrityError):
            Membership.objects.create(user=user, brand=brand, role=Membership.Role.VIEWER)

    def test_membership_roles(self):
        assert len(Membership.Role.choices) == 3
        assert Membership.Role.OWNER == "owner"
        assert Membership.Role.EDITOR == "editor"
        assert Membership.Role.VIEWER == "viewer"

    def test_user_multiple_brands(self, user):
        b1 = Brand.objects.create(name="B1", slug="b1")
        b2 = Brand.objects.create(name="B2", slug="b2")
        Membership.objects.create(user=user, brand=b1, role=Membership.Role.OWNER)
        Membership.objects.create(user=user, brand=b2, role=Membership.Role.VIEWER)
        assert user.memberships.count() == 2


@pytest.mark.django_db
class TestBrandAIDefaultsForm:
    def test_form_saves_provider_and_model_to_json(self, brand):
        from apps.brands.admin import BrandAIDefaultsForm

        data = {
            "name": brand.name,
            "slug": brand.slug,
            "default_language": "es",
            "is_active": True,
            "ai_text_provider": "gemini",
            "ai_text_model": "gemini-2.5-flash",
            "ai_text_model_custom": "",
            "ai_image_provider": "imagen",
            "ai_image_model": "imagen-4.0-generate-001",
            "ai_image_model_custom": "",
        }
        form = BrandAIDefaultsForm(data, instance=brand)
        assert form.is_valid(), form.errors
        saved = form.save()

        defaults = saved.ai_provider_defaults
        assert defaults["text"]["default"]["provider"] == "gemini"
        assert defaults["text"]["default"]["model"] == "gemini-2.5-flash"
        assert defaults["image"]["default"]["provider"] == "imagen"
        assert defaults["image"]["default"]["model"] == "imagen-4.0-generate-001"

    def test_form_custom_model(self, brand):
        from apps.brands.admin import BrandAIDefaultsForm

        data = {
            "name": brand.name,
            "slug": brand.slug,
            "default_language": "es",
            "is_active": True,
            "ai_text_provider": "openai",
            "ai_text_model": "__custom__",
            "ai_text_model_custom": "gpt-future-99",
            "ai_image_provider": "",
            "ai_image_model": "",
            "ai_image_model_custom": "",
        }
        form = BrandAIDefaultsForm(data, instance=brand)
        assert form.is_valid(), form.errors
        saved = form.save()

        assert saved.ai_provider_defaults["text"]["default"]["model"] == "gpt-future-99"
        assert "image" not in saved.ai_provider_defaults

    def test_form_preserves_per_agent_overrides(self, brand):
        from apps.brands.admin import BrandAIDefaultsForm

        brand.ai_provider_defaults = {
            "text": {
                "carousel": {"provider": "gemini", "model": "gemini-2.5-pro"},
                "default": {"provider": "openai", "model": "gpt-4o"},
            }
        }
        brand.save()

        data = {
            "name": brand.name,
            "slug": brand.slug,
            "default_language": "es",
            "is_active": True,
            "ai_text_provider": "openai",
            "ai_text_model": "gpt-5.4-mini",
            "ai_text_model_custom": "",
            "ai_image_provider": "",
            "ai_image_model": "",
            "ai_image_model_custom": "",
        }
        form = BrandAIDefaultsForm(data, instance=brand)
        assert form.is_valid(), form.errors
        saved = form.save()

        defaults = saved.ai_provider_defaults
        # Per-agent override preserved
        assert defaults["text"]["carousel"]["provider"] == "gemini"
        assert defaults["text"]["carousel"]["model"] == "gemini-2.5-pro"
        # Default updated
        assert defaults["text"]["default"]["provider"] == "openai"
        assert defaults["text"]["default"]["model"] == "gpt-5.4-mini"

    def test_form_clears_defaults_when_empty(self, brand):
        from apps.brands.admin import BrandAIDefaultsForm

        brand.ai_provider_defaults = {
            "text": {"default": {"provider": "openai", "model": "gpt-4o"}}
        }
        brand.save()

        data = {
            "name": brand.name,
            "slug": brand.slug,
            "default_language": "es",
            "is_active": True,
            "ai_text_provider": "",
            "ai_text_model": "",
            "ai_text_model_custom": "",
            "ai_image_provider": "",
            "ai_image_model": "",
            "ai_image_model_custom": "",
        }
        form = BrandAIDefaultsForm(data, instance=brand)
        assert form.is_valid(), form.errors
        saved = form.save()

        assert saved.ai_provider_defaults == {}

    def test_form_init_prepopulates_from_existing(self, brand):
        from apps.brands.admin import BrandAIDefaultsForm

        brand.ai_provider_defaults = {
            "text": {"default": {"provider": "gemini", "model": "gemini-2.5-flash"}},
            "image": {"default": {"provider": "openai", "model": "gpt-image-1"}},
        }
        brand.save()

        form = BrandAIDefaultsForm(instance=brand)
        assert form.fields["ai_text_provider"].initial == "gemini"
        assert form.fields["ai_text_model"].initial == "gemini-2.5-flash"
        assert form.fields["ai_image_provider"].initial == "openai"
        assert form.fields["ai_image_model"].initial == "gpt-image-1"
