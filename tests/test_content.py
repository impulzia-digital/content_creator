"""Tests para apps.content — ContentBrief, ContentVariant, AgentRun."""

import pytest
from django.template import Context, Template
from django.utils import timezone

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
        assert brief.seed_key is None
        assert brief.scheduled_for is None

    def test_brief_enriched_brief_json(self, enriched_brief):
        assert enriched_brief.enriched_brief["tema"] == "Clean code para desarrolladores junior"
        assert len(enriched_brief.enriched_brief["hooks"]) == 3
        assert enriched_brief.status == ContentBrief.Status.READY

    def test_brief_for_brand(self, brand, brief):
        assert ContentBrief.objects.for_brand(brand).count() == 1

    def test_brief_ordering(self, brand, user):
        b1 = ContentBrief.objects.create(brand=brand, title="A", raw_idea="a", created_by=user)
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
        v1 = ContentVariant.objects.create(brief=brief, version=1)
        v2 = ContentVariant.objects.create(brief=brief, version=2)
        v3 = ContentVariant.objects.create(brief=brief, version=3)
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
