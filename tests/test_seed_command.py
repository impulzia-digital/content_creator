"""Tests para el command seed_business_data."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.brands.models import Brand, InstagramAccount, Membership
from apps.content.models import ContentBrief


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_seed_dir(tmp_path, *, include_instagram=False, password_env="TEST_SEED_OWNER_PASSWORD"):
    root = tmp_path / "business"
    brand_dir = root / "acme"
    brand_dir.mkdir(parents=True)

    _write_json(
        brand_dir / "brand.json",
        {
            "slug": "acme",
            "name": "ACME",
            "description": "Marca seeded para tests",
            "tagline": "Operaciones claras",
            "industry": "Consultoría",
            "target_audience": "Equipos comerciales y de marketing",
            "brand_voice_prompt": "Habla claro y directo.",
            "tone_adjectives": ["claro", "directo"],
            "tone_description": "Sin relleno",
            "forbidden_words": ["milagro"],
            "color_primary": "#111827",
            "color_secondary": "#1D4ED8",
            "color_background": "#F9FAFB",
            "color_accent": "#F97316",
            "color_text": "#111827",
            "default_hashtags": ["#ACME"],
            "default_language": "es",
            "preferred_image_style": "minimalista",
            "preferred_aspect_ratios": ["4:5", "9:16"],
            "is_active": True,
        },
    )
    _write_json(
        brand_dir / "users.json",
        [
            {
                "username": "owner",
                "email": "owner@acme.local",
                "first_name": "Seed",
                "last_name": "Owner",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "password_env": password_env,
            }
        ],
    )
    _write_json(
        brand_dir / "memberships.json",
        [
            {
                "username": "owner",
                "role": "owner",
            }
        ],
    )
    _write_json(
        brand_dir / "briefs.json",
        [
            {
                "seed_key": "hero-post",
                "title": "Post hero",
                "raw_idea": "Explicar el problema central del cliente ideal.",
                "content_type": "post",
                "aspect_ratio": "4:5",
                "num_slides": 1,
                "status": "draft",
                "priority": 2,
                "tags": ["hero"],
                "created_by_username": "owner",
            },
            {
                "seed_key": "carousel-dolor",
                "title": "Carrusel dolor",
                "raw_idea": "Explicar un dolor y como resolverlo.",
                "content_type": "carousel",
                "aspect_ratio": "4:5",
                "num_slides": 4,
                "status": "draft",
                "priority": 3,
                "tags": ["educacion"],
                "created_by_username": "owner",
            },
        ],
    )

    instagram_payload = []
    if include_instagram:
        instagram_payload = [
            {
                "ig_user_id": "17841400000000001",
                "username": "acme_ig",
                "page_id": "100000000000001",
                "access_token_env": "TEST_INSTAGRAM_ACCESS_TOKEN",
                "is_active": True,
            }
        ]
    _write_json(brand_dir / "instagram_accounts.json", instagram_payload)

    return root, brand_dir


@pytest.mark.django_db
class TestSeedBusinessDataCommand:
    def test_seed_command_creates_brand_users_memberships_accounts_and_briefs(self, tmp_path, monkeypatch):
        seed_root, _ = _build_seed_dir(tmp_path, include_instagram=True)
        monkeypatch.setenv("TEST_SEED_OWNER_PASSWORD", "owner-pass-123")
        monkeypatch.setenv("TEST_INSTAGRAM_ACCESS_TOKEN", "EAAtesttoken")

        call_command("seed_business_data", seed_dir=str(seed_root))

        user_model = get_user_model()
        owner = user_model.objects.get(username="owner")
        brand = Brand.objects.get(slug="acme")
        brief = ContentBrief.objects.get(brand=brand, seed_key="hero-post")

        assert owner.email == "owner@acme.local"
        assert owner.check_password("owner-pass-123") is True
        assert Membership.objects.get(user=owner, brand=brand).role == Membership.Role.OWNER
        assert InstagramAccount.objects.get(brand=brand, ig_user_id="17841400000000001").username == "acme_ig"
        assert brief.title == "Post hero"
        assert brief.created_by == owner
        assert brief.tags == ["hero"]

    def test_seed_command_is_idempotent_and_updates_existing_records(self, tmp_path, monkeypatch):
        seed_root, brand_dir = _build_seed_dir(tmp_path)
        monkeypatch.setenv("TEST_SEED_OWNER_PASSWORD", "owner-pass-123")

        call_command("seed_business_data", seed_dir=str(seed_root))

        _write_json(
            brand_dir / "brand.json",
            {
                "slug": "acme",
                "name": "ACME Updated",
                "description": "Marca actualizada",
                "tagline": "Operaciones claras",
                "industry": "Consultoría",
                "target_audience": "Equipos B2B",
                "brand_voice_prompt": "Habla con foco en rentabilidad.",
                "tone_adjectives": ["directo"],
                "tone_description": "Sin relleno",
                "forbidden_words": ["milagro"],
                "color_primary": "#111827",
                "color_secondary": "#1D4ED8",
                "color_background": "#F9FAFB",
                "color_accent": "#F97316",
                "color_text": "#111827",
                "default_hashtags": ["#ACME"],
                "default_language": "es",
                "preferred_image_style": "minimalista",
                "preferred_aspect_ratios": ["4:5", "9:16"],
                "is_active": True,
            },
        )
        _write_json(
            brand_dir / "briefs.json",
            [
                {
                    "seed_key": "hero-post",
                    "title": "Post hero actualizado",
                    "raw_idea": "Nueva version del problema central.",
                    "content_type": "post",
                    "aspect_ratio": "4:5",
                    "num_slides": 1,
                    "status": "draft",
                    "priority": 1,
                    "tags": ["hero", "update"],
                    "created_by_username": "owner",
                },
                {
                    "seed_key": "carousel-dolor",
                    "title": "Carrusel dolor",
                    "raw_idea": "Explicar un dolor y como resolverlo.",
                    "content_type": "carousel",
                    "aspect_ratio": "4:5",
                    "num_slides": 4,
                    "status": "draft",
                    "priority": 3,
                    "tags": ["educacion"],
                    "created_by_username": "owner",
                },
            ],
        )

        call_command("seed_business_data", seed_dir=str(seed_root))

        brand = Brand.objects.get(slug="acme")
        brief = ContentBrief.objects.get(brand=brand, seed_key="hero-post")

        assert Brand.objects.count() == 1
        assert ContentBrief.objects.count() == 2
        assert brand.name == "ACME Updated"
        assert brief.title == "Post hero actualizado"
        assert brief.priority == 1
        assert brief.tags == ["hero", "update"]

    def test_seed_command_dry_run_does_not_persist_changes(self, tmp_path, monkeypatch):
        seed_root, _ = _build_seed_dir(tmp_path)
        monkeypatch.setenv("TEST_SEED_OWNER_PASSWORD", "owner-pass-123")

        call_command("seed_business_data", seed_dir=str(seed_root), dry_run=True)

        assert Brand.objects.count() == 0
        assert ContentBrief.objects.count() == 0

    def test_seed_command_rolls_back_when_secret_env_is_missing(self, tmp_path, monkeypatch):
        seed_root, _ = _build_seed_dir(tmp_path)
        monkeypatch.delenv("TEST_SEED_OWNER_PASSWORD", raising=False)

        with pytest.raises(CommandError, match="TEST_SEED_OWNER_PASSWORD"):
            call_command("seed_business_data", seed_dir=str(seed_root))

        assert Brand.objects.count() == 0
        assert ContentBrief.objects.count() == 0

    def test_seed_command_fails_when_membership_references_unknown_user(self, tmp_path, monkeypatch):
        seed_root, brand_dir = _build_seed_dir(tmp_path)
        monkeypatch.setenv("TEST_SEED_OWNER_PASSWORD", "owner-pass-123")
        _write_json(
            brand_dir / "memberships.json",
            [
                {
                    "username": "ghost",
                    "role": "owner",
                }
            ],
        )

        with pytest.raises(CommandError, match="ghost"):
            call_command("seed_business_data", seed_dir=str(seed_root))

        assert Brand.objects.count() == 0
        assert Membership.objects.count() == 0