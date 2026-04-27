"""Tests para apps.content — ContentBrief, ContentVariant, AgentRun."""

import pytest
from unittest.mock import patch
from django.template import Context, Template
from django.urls import reverse

from apps.assets.models import Asset
from apps.content.models import AgentRun, ContentBrief, ContentVariant


@pytest.mark.django_db
class TestContentBrief:
    def test_create_brief(self, brief):
        assert brief.pk is not None
        assert brief.status == ContentBrief.Status.DRAFT
        assert brief.content_type == ContentBrief.ContentType.POST

    def test_brief_str(self, brief):
        s = str(brief)
        assert "Post" in s
        assert "5 consejos" in s

    def test_brief_uuid_pk(self, brief):
        assert len(str(brief.pk)) == 36

    def test_brief_status_choices(self):
        statuses = [c[0] for c in ContentBrief.Status.choices]
        assert "draft" in statuses
        assert "generating" in statuses
        assert "review" in statuses
        assert "published" in statuses
        assert "failed" in statuses

    def test_brief_content_types(self):
        types = [c[0] for c in ContentBrief.ContentType.choices]
        assert "post" in types
        assert "carousel" in types
        assert "reel" in types
        assert "story" in types

    def test_brief_defaults(self, brief):
        assert brief.aspect_ratio == "4:5"
        assert brief.num_slides == 1
        assert brief.tags == []
        assert brief.enriched_brief is None
        assert brief.ai_provider_overrides == {}
        assert brief.seed_key is None
        assert brief.scheduled_for is None

    def test_brief_enriched_brief_json(self, enriched_brief):
        assert enriched_brief.enriched_brief["tema"] == "Clean code para desarrolladores junior"
        assert len(enriched_brief.enriched_brief["hooks"]) == 3
        assert enriched_brief.status == ContentBrief.Status.READY

    def test_brief_for_brand(self, brand, brief):
        assert ContentBrief.objects.for_brand(brand).count() == 1

    def test_brief_ordering(self, brand, user):
        ContentBrief.objects.create(brand=brand, title="A", raw_idea="a", created_by=user)
        b2 = ContentBrief.objects.create(brand=brand, title="B", raw_idea="b", created_by=user)
        briefs = list(ContentBrief.objects.all())
        assert briefs[0] == b2  # Más reciente primero

    def test_brief_seed_key_unique_per_brand(self, brand, user):
        from django.db import IntegrityError

        ContentBrief.objects.create(
            brand=brand,
            created_by=user,
            title="Primero",
            seed_key="hero-post",
            raw_idea="uno",
        )

        with pytest.raises(IntegrityError):
            ContentBrief.objects.create(
                brand=brand,
                created_by=user,
                title="Duplicado",
                seed_key="hero-post",
                raw_idea="dos",
            )


@pytest.mark.django_db
class TestContentVariant:
    def test_create_variant(self, variant):
        assert variant.pk is not None
        assert variant.version == 1
        assert variant.is_selected is False

    def test_variant_str(self, variant):
        s = str(variant)
        assert "v1" in s

    def test_variant_uuid_pk(self, variant):
        assert len(str(variant.pk)) == 36

    def test_variant_unique_version_per_brief(self, brief, variant):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ContentVariant.objects.create(brief=brief, version=1)

    def test_multiple_variants(self, brief):
        ContentVariant.objects.create(brief=brief, version=1)
        ContentVariant.objects.create(brief=brief, version=2)
        ContentVariant.objects.create(brief=brief, version=3)
        assert brief.variants.count() == 3

    def test_variant_defaults(self, brief):
        v = ContentVariant.objects.create(brief=brief, version=1)
        assert v.caption == ""
        assert v.hashtags == []
        assert v.alt_text == ""
        assert v.generation_params == {}
        assert v.generation_cost_usd == 0

    def test_variant_generation_cost(self, brief):
        v = ContentVariant.objects.create(
            brief=brief, version=1, generation_cost_usd=0.0523
        )
        assert float(v.generation_cost_usd) == 0.0523


@pytest.mark.django_db
class TestAgentRun:
    def test_create_agent_run(self, brief):
        run = AgentRun.objects.create(
            brief=brief,
            agent_type=AgentRun.AgentType.COPY,
            status=AgentRun.RunStatus.SUCCESS,
            provider="openai",
            model_used="gpt-4o-mini",
            duration_seconds=2.5,
            cost_usd=0.0003,
        )
        assert run.pk is not None
        assert run.agent_type == "copy"

    def test_agent_run_str(self, brief):
        run = AgentRun.objects.create(
            brief=brief,
            agent_type=AgentRun.AgentType.IMAGE,
            status=AgentRun.RunStatus.RUNNING,
        )
        s = str(run)
        assert "Image Agent" in s

    def test_agent_run_types(self):
        types = [c[0] for c in AgentRun.AgentType.choices]
        assert "brief_enricher" in types
        assert "copy" in types
        assert "image" in types
        assert "carousel" in types
        assert "video" in types
        assert "hashtag" in types

    def test_agent_run_statuses(self):
        statuses = [c[0] for c in AgentRun.RunStatus.choices]
        assert "pending" in statuses
        assert "running" in statuses
        assert "success" in statuses
        assert "failed" in statuses

    def test_agent_run_defaults(self, brief):
        run = AgentRun.objects.create(
            brief=brief, agent_type=AgentRun.AgentType.COPY
        )
        assert run.status == AgentRun.RunStatus.PENDING
        assert run.attempt == 1
        assert run.max_attempts == 3
        assert run.input_data == {}
        assert run.output_data == {}

    def test_agent_run_with_variant(self, brief, variant):
        run = AgentRun.objects.create(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.COPY,
        )
        assert run.variant == variant

    def test_agent_runs_per_brief(self, brief):
        AgentRun.objects.create(brief=brief, agent_type=AgentRun.AgentType.BRIEF_ENRICHER)
        AgentRun.objects.create(brief=brief, agent_type=AgentRun.AgentType.COPY)
        AgentRun.objects.create(brief=brief, agent_type=AgentRun.AgentType.IMAGE)
        assert brief.agent_runs.count() == 3


@pytest.mark.django_db
class TestBriefTotalCost:
    def test_total_cost_sums_successful_runs(self, brief):
        AgentRun.objects.create(
            brief=brief, agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            status=AgentRun.RunStatus.SUCCESS, cost_usd=0.0010,
        )
        AgentRun.objects.create(
            brief=brief, agent_type=AgentRun.AgentType.IMAGE,
            status=AgentRun.RunStatus.SUCCESS, cost_usd=0.0400,
        )
        AgentRun.objects.create(
            brief=brief, agent_type=AgentRun.AgentType.COPY,
            status=AgentRun.RunStatus.SUCCESS, cost_usd=0.0005,
        )
        assert float(brief.total_cost_usd) == pytest.approx(0.0415, abs=1e-4)

    def test_total_cost_excludes_failed_runs(self, brief):
        AgentRun.objects.create(
            brief=brief, agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            status=AgentRun.RunStatus.FAILED, cost_usd=0.0,
        )
        AgentRun.objects.create(
            brief=brief, agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            status=AgentRun.RunStatus.SUCCESS, cost_usd=0.0010,
        )
        assert float(brief.total_cost_usd) == pytest.approx(0.0010, abs=1e-4)

    def test_total_cost_zero_when_no_runs(self, brief):
        assert brief.total_cost_usd == 0


class TestFormatCostFilter:
    def test_format_cost_zero(self):
        template = Template("{% load content_extras %}{{ value|format_cost }}")
        assert template.render(Context({"value": 0})) == "$0.00"

    def test_format_cost_small(self):
        template = Template("{% load content_extras %}{{ value|format_cost }}")
        assert template.render(Context({"value": 0.0012})) == "$0.0012"

    def test_format_cost_medium(self):
        template = Template("{% load content_extras %}{{ value|format_cost }}")
        assert template.render(Context({"value": 0.08})) == "$0.08"

    def test_format_cost_large(self):
        template = Template("{% load content_extras %}{{ value|format_cost }}")
        assert template.render(Context({"value": 1.23})) == "$1.23"

    def test_format_cost_none(self):
        template = Template("{% load content_extras %}{{ value|format_cost }}")
        assert template.render(Context({"value": None})) == "$0.00"


class TestContentTemplateFilters:
    def test_is_list_filter_does_not_split_strings(self):
        template = Template(
            "{% load content_extras %}{% if value|is_list %}{{ value|join:', ' }}{% else %}{{ value }}{% endif %}"
        )

        rendered = template.render(Context({"value": "Presentación de Impulzia"}))

        assert rendered == "Presentación de Impulzia"

    def test_is_list_filter_joins_lists(self):
        template = Template(
            "{% load content_extras %}{% if value|is_list %}{{ value|join:', ' }}{% else %}{{ value }}{% endif %}"
        )

        rendered = template.render(Context({"value": ["uno", "dos"]}))

        assert rendered == "uno, dos"


@pytest.mark.django_db
class TestBriefCreateView:
    def test_get_context_has_model_catalog(self, client, brand, user, membership):
        import json

        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

        response = client.get(reverse("content:brief_create"))

        assert response.status_code == 200
        assert "model_catalog_json" in response.context
        catalog = json.loads(response.context["model_catalog_json"])
        assert "openai" in catalog
        assert "gemini" in catalog
        assert "imagen" in catalog

    def test_get_context_has_provider_choices(self, client, brand, user, membership):
        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

        response = client.get(reverse("content:brief_create"))

        assert response.status_code == 200
        choices = response.context["provider_choices"]
        provider_values = [v for v, _ in choices]
        assert "openai" in provider_values
        assert "gemini" in provider_values
        assert "imagen" in provider_values

    def test_post_with_model_selector(self, client, brand, user, membership):
        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

        response = client.post(reverse("content:brief_create"), {
            "title": "Test selector",
            "raw_idea": "Testing model selector",
            "content_type": "post",
            "aspect_ratio": "4:5",
            "num_slides": "1",
            "priority": "5",
            "text_provider_override": "gemini",
            "text_model_select": "gemini-2.5-flash",
            "image_provider_override": "imagen",
            "image_model_select": "imagen-4.0-generate-001",
        })

        assert response.status_code == 302
        brief = ContentBrief.objects.get(title="Test selector")
        assert brief.ai_provider_overrides["text"]["default"]["provider"] == "gemini"
        assert brief.ai_provider_overrides["text"]["default"]["model"] == "gemini-2.5-flash"
        assert brief.ai_provider_overrides["image"]["default"]["provider"] == "imagen"
        assert brief.ai_provider_overrides["image"]["default"]["model"] == "imagen-4.0-generate-001"

    def test_post_with_image_resolution_preset(self, client, brand, user, membership):
        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

        response = client.post(reverse("content:brief_create"), {
            "title": "Test resolution preset",
            "raw_idea": "Testing image resolution preset",
            "content_type": "post",
            "aspect_ratio": "16:9",
            "num_slides": "1",
            "priority": "5",
            "image_resolution_preset": "2k",
        })

        assert response.status_code == 302
        brief = ContentBrief.objects.get(title="Test resolution preset")
        image_defaults = brief.ai_provider_overrides["image"]["default"]
        assert image_defaults["resolution_preset"] == "2k"
        assert image_defaults["width"] == 2048
        assert image_defaults["height"] == 1152

    def test_post_with_custom_model(self, client, brand, user, membership):
        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

        response = client.post(reverse("content:brief_create"), {
            "title": "Test custom",
            "raw_idea": "Testing custom model",
            "content_type": "post",
            "aspect_ratio": "4:5",
            "num_slides": "1",
            "priority": "5",
            "text_provider_override": "openai",
            "text_model_select": "__custom__",
            "text_model_custom": "gpt-future-99",
        })

        assert response.status_code == 302
        brief = ContentBrief.objects.get(title="Test custom")
        assert brief.ai_provider_overrides["text"]["default"]["model"] == "gpt-future-99"

    def test_post_no_overrides(self, client, brand, user, membership):
        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

        response = client.post(reverse("content:brief_create"), {
            "title": "Test no override",
            "raw_idea": "No AI overrides",
            "content_type": "post",
            "aspect_ratio": "4:5",
            "num_slides": "1",
            "priority": "5",
        })

        assert response.status_code == 302
        brief = ContentBrief.objects.get(title="Test no override")
        assert brief.ai_provider_overrides == {}


@pytest.mark.django_db
class TestBriefDetailAndGenerateView:
    def _activate_brand(self, client, brand, user):
        client.force_login(user)
        session = client.session
        session["active_brand_id"] = brand.pk
        session.save()

    def test_detail_flags_incomplete_reel_generation(self, client, reel_brief, brand, user, membership):
        reel_brief.status = ContentBrief.Status.REVIEW
        reel_brief.save(update_fields=["status"])

        variant = ContentVariant.objects.create(brief=reel_brief, version=1)
        variant.caption = "Caption without rendered video"
        variant.save(update_fields=["caption"])

        self._activate_brand(client, brand, user)
        response = client.get(reverse("content:brief_detail", args=[reel_brief.pk]))

        assert response.status_code == 200
        assert response.context["generation_incomplete"] is True
        assert response.context["can_generate"] is True
        assert "sin asset de video" in response.context["missing_output_message"]

    def test_generate_allows_incomplete_reel_regeneration(self, client, reel_brief, brand, user, membership):
        reel_brief.status = ContentBrief.Status.REVIEW
        reel_brief.save(update_fields=["status"])
        ContentVariant.objects.create(brief=reel_brief, version=1)

        self._activate_brand(client, brand, user)

        with patch("apps.content.views.generate_content_task.delay") as mock_delay:
            response = client.post(reverse("content:brief_generate", args=[reel_brief.pk]))

        reel_brief.refresh_from_db()
        assert response.status_code == 302
        assert reel_brief.status == ContentBrief.Status.GENERATING
        mock_delay.assert_called_once_with(str(reel_brief.pk))

    def test_generate_keeps_review_locked_when_reel_has_video(self, client, reel_brief, brand, user, membership, variant):
        reel_brief.status = ContentBrief.Status.REVIEW
        reel_brief.save(update_fields=["status"])
        variant.brief = reel_brief
        variant.save(update_fields=["brief"])
        Asset.objects.create(
            variant=variant,
            asset_type=Asset.AssetType.VIDEO,
            file_url="https://cdn.example.com/reel.mp4",
            file_key="brands/test/reel.mp4",
            mime_type="video/mp4",
        )

        self._activate_brand(client, brand, user)
        response = client.post(reverse("content:brief_generate", args=[reel_brief.pk]))

        reel_brief.refresh_from_db()
        assert response.status_code == 302
        assert reel_brief.status == ContentBrief.Status.REVIEW
