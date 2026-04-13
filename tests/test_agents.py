"""Tests para apps.agents — BaseAgent, todos los sub-agentes, orchestrator."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.agents.brief_enricher import BriefEnricherAgent
from apps.agents.copy_agent import CopyAgent
from apps.agents.hashtag_agent import HashtagAgent
from apps.agents.image_agent import ImageAgent, ASPECT_RATIOS
from apps.agents.carousel_agent import CarouselAgent
from apps.agents.video_agent import VideoAgent
from apps.agents.orchestrator import ContentOrchestrator
from apps.content.models import AgentRun, ContentBrief, ContentVariant
from apps.integrations.base import (
    ImageGenerationResponse,
    TextGenerationResponse,
    UploadResult,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ── AgentContext ──────────────────────────────────────────────


class TestAgentContext:
    def test_context_creation(self, brief, brand):
        ctx = AgentContext(brief=brief, brand=brand)
        assert ctx.brief == brief
        assert ctx.brand == brand
        assert ctx.variant is None
        assert ctx.extra == {}

    def test_context_brand_briefing(self, brief, brand):
        ctx = AgentContext(brief=brief, brand=brand)
        briefing = ctx.brand_briefing
        assert "Test Brand" in briefing
        assert "Technology" in briefing

    def test_context_with_variant(self, brief, brand, variant):
        ctx = AgentContext(brief=brief, brand=brand, variant=variant)
        assert ctx.variant == variant


# ── AgentResult ───────────────────────────────────────────────


class TestAgentResult:
    def test_success_result(self):
        r = AgentResult(success=True, data={"key": "val"}, cost_usd=0.01)
        assert r.success is True
        assert r.error == ""

    def test_failure_result(self):
        r = AgentResult(success=False, error="API timeout")
        assert r.success is False
        assert r.data == {}


# ── BriefEnricherAgent ───────────────────────────────────────


class TestBriefEnricherAgent:
    @pytest.fixture
    def agent(self):
        return BriefEnricherAgent()

    @pytest.mark.asyncio
    async def test_build_prompt(self, agent, brief, brand):
        ctx = AgentContext(brief=brief, brand=brand)
        system, user = await agent.build_prompt(ctx)
        assert "estratega de contenido" in system
        assert "Test Brand" in system
        assert brief.raw_idea in user
        assert "JSON" in user

    @pytest.mark.asyncio
    async def test_parse_output_json_string(self, agent, brief, brand):
        ctx = AgentContext(brief=brief, brand=brand)
        data = await agent.parse_output('{"tema": "test"}', ctx)
        assert data == {"tema": "test"}

    @pytest.mark.asyncio
    async def test_parse_output_dict(self, agent, brief, brand):
        ctx = AgentContext(brief=brief, brand=brand)
        data = await agent.parse_output({"tema": "test"}, ctx)
        assert data == {"tema": "test"}

    @pytest.mark.asyncio
    async def test_execute_success(self, agent, brief, brand):
        mock_response = TextGenerationResponse(
            text=json.dumps({
                "tema": "Clean code",
                "angulo": "Errores comunes",
                "objetivo": "Educar",
                "formato_sugerido": "post",
                "num_slides_sugerido": 1,
                "hooks": ["Hook 1"],
                "puntos_clave": ["Punto 1"],
                "cta": "Guarda este post",
                "keywords": ["clean code"],
                "tono_especifico": "educativo",
                "referencia_visual": "dark theme",
                "audiencia_objetivo": "devs junior",
            }),
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=200,
            cost_usd=0.0002,
        )

        ctx = AgentContext(brief=brief, brand=brand)

        with patch(
            "apps.agents.brief_enricher.get_text_provider"
        ) as mock_get:
            mock_provider = AsyncMock()
            mock_provider.generate.return_value = mock_response
            mock_get.return_value = mock_provider

            result = await agent.execute(ctx)

        assert result.success is True
        assert result.data["tema"] == "Clean code"
        assert result.cost_usd == 0.0002

        # Verify brief was updated
        await brief.arefresh_from_db()
        assert brief.enriched_brief is not None
        assert brief.enriched_brief["tema"] == "Clean code"

        # Verify AgentRun was created
        assert await AgentRun.objects.filter(
            brief=brief, agent_type="brief_enricher"
        ).aexists()

    @pytest.mark.asyncio
    async def test_execute_failure_creates_failed_run(self, agent, brief, brand):
        ctx = AgentContext(brief=brief, brand=brand)

        with patch(
            "apps.agents.brief_enricher.get_text_provider"
        ) as mock_get:
            mock_provider = AsyncMock()
            mock_provider.generate.side_effect = Exception("API down")
            mock_get.return_value = mock_provider

            result = await agent.execute(ctx)

        assert result.success is False
        assert "API down" in result.error

        run = await AgentRun.objects.filter(brief=brief, agent_type="brief_enricher").afirst()
        assert run is not None
        assert run.status == "failed"
        assert "API down" in run.error_detail


# ── CopyAgent ─────────────────────────────────────────────────


class TestCopyAgent:
    @pytest.fixture
    def agent(self):
        return CopyAgent()

    @pytest.mark.asyncio
    async def test_build_prompt(self, agent, enriched_brief, brand):
        ctx = AgentContext(brief=enriched_brief, brand=brand)
        system, user = await agent.build_prompt(ctx)
        assert "copywriter" in system.lower()
        assert "2200" in system  # limit chars
        assert "Clean code" in user

    @pytest.mark.asyncio
    async def test_execute_updates_variant(self, agent, enriched_brief, brand, variant):
        mock_response = TextGenerationResponse(
            text=json.dumps({
                "caption": "El 90% de los devs junior cometen estos errores...",
                "alt_text": "Clean code tips infographic",
                "hook_line": "El 90% de los devs junior cometen estos errores",
            }),
            model="gpt-4o-mini",
            cost_usd=0.0001,
        )
        ctx = AgentContext(brief=enriched_brief, brand=brand, variant=variant)

        with patch("apps.agents.copy_agent.get_text_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.generate.return_value = mock_response
            mock_get.return_value = mock_provider

            result = await agent.execute(ctx)

        assert result.success is True
        await variant.arefresh_from_db()
        assert "90%" in variant.caption
        assert variant.alt_text == "Clean code tips infographic"


# ── HashtagAgent ──────────────────────────────────────────────


class TestHashtagAgent:
    @pytest.fixture
    def agent(self):
        return HashtagAgent()

    @pytest.mark.asyncio
    async def test_build_prompt_includes_brand_hashtags(self, agent, enriched_brief, brand):
        ctx = AgentContext(brief=enriched_brief, brand=brand)
        system, user = await agent.build_prompt(ctx)
        assert "#testbrand" in system
        assert "20-30" in system

    @pytest.mark.asyncio
    async def test_execute_saves_hashtags(self, agent, enriched_brief, brand, variant):
        mock_response = TextGenerationResponse(
            text=json.dumps({
                "hashtags": ["#python", "#cleancode", "#devtips"],
                "hashtag_groups": {
                    "brand": ["#testbrand"],
                    "high_volume": ["#python"],
                    "medium_volume": ["#cleancode"],
                    "niche": ["#devtips"],
                },
            }),
            model="gpt-4o-mini",
            cost_usd=0.0001,
        )
        ctx = AgentContext(brief=enriched_brief, brand=brand, variant=variant)

        with patch("apps.agents.hashtag_agent.get_text_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.generate.return_value = mock_response
            mock_get.return_value = mock_provider

            result = await agent.execute(ctx)

        assert result.success is True
        await variant.arefresh_from_db()
        assert "#python" in variant.hashtags


# ── ImageAgent ────────────────────────────────────────────────


class TestImageAgent:
    @pytest.fixture
    def agent(self):
        return ImageAgent()

    def test_aspect_ratios_mapping(self):
        assert ASPECT_RATIOS["1:1"] == (1080, 1080)
        assert ASPECT_RATIOS["4:5"] == (1080, 1350)
        assert ASPECT_RATIOS["9:16"] == (1080, 1920)
        assert ASPECT_RATIOS["16:9"] == (1920, 1080)

    @pytest.mark.asyncio
    async def test_build_prompt(self, agent, enriched_brief, brand):
        ctx = AgentContext(brief=enriched_brief, brand=brand)
        system, user = await agent.build_prompt(ctx)
        assert "director de arte" in system
        assert "4:5" in user
        assert brand.color_primary in user

    @pytest.mark.asyncio
    async def test_execute_creates_asset(self, agent, enriched_brief, brand, variant):
        from apps.assets.models import Asset

        prompt_response = TextGenerationResponse(
            text=json.dumps({
                "image_prompt": "A clean minimalist code editor on dark background",
                "negative_prompt": "blurry, low quality",
                "style_notes": "modern, dark theme",
            }),
            model="gpt-4o-mini",
            cost_usd=0.0001,
        )
        image_response = ImageGenerationResponse(
            image_urls=["https://oai.example.com/generated.jpg"],
            model="gpt-image-1",
            cost_usd=0.04,
        )
        upload_result = UploadResult(
            url="https://cdn.example.com/img.jpg",
            key="brands/test/content/abc/img.jpg",
            size_bytes=150000,
        )

        ctx = AgentContext(brief=enriched_brief, brand=brand, variant=variant)

        with patch("apps.agents.image_agent.get_text_provider") as mock_text, \
             patch("apps.agents.image_agent.get_image_provider") as mock_img, \
             patch("apps.agents.image_agent.get_storage_provider") as mock_storage:
            mock_text.return_value = AsyncMock(generate=AsyncMock(return_value=prompt_response))
            mock_img.return_value = AsyncMock(generate=AsyncMock(return_value=image_response))
            mock_storage.return_value = AsyncMock(upload_from_url=AsyncMock(return_value=upload_result))

            result = await agent.execute(ctx)

        assert result.success is True
        assert result.data["num_images"] == 1
        assert await Asset.objects.filter(variant=variant).acount() == 1

        asset = await Asset.objects.aget(variant=variant)
        assert asset.file_url == "https://cdn.example.com/img.jpg"
        assert asset.width == 1080
        assert asset.height == 1350


# ── CarouselAgent ─────────────────────────────────────────────


class TestCarouselAgent:
    @pytest.fixture
    def agent(self):
        return CarouselAgent()

    @pytest.mark.asyncio
    async def test_build_prompt(self, agent, carousel_brief, brand):
        carousel_brief.enriched_brief = {"tema": "Testing en Python", "angulo": "Tutorial"}
        await carousel_brief.asave()
        ctx = AgentContext(brief=carousel_brief, brand=brand)
        system, user = await agent.build_prompt(ctx)
        assert "PORTADA" in system
        assert "PROBLEMA" in system
        assert "CTA" in system
        assert "7" in user  # num_slides

    @pytest.mark.asyncio
    async def test_execute_creates_multiple_assets(self, agent, carousel_brief, brand):
        from apps.assets.models import Asset

        carousel_brief.enriched_brief = {"tema": "Testing", "angulo": "Guía"}
        await carousel_brief.asave()

        variant = await ContentVariant.objects.acreate(brief=carousel_brief, version=1)

        carousel_structure = {
            "slides": [
                {"slide_number": i, "slide_type": "contenido",
                 "headline": f"Slide {i}", "body": "Body",
                 "visual_description": "A slide", "design_notes": "clean"}
                for i in range(1, 4)  # 3 slides for test speed
            ],
            "visual_style": "modern",
            "color_scheme": "blue",
        }

        structure_response = TextGenerationResponse(
            text=json.dumps(carousel_structure),
            model="gpt-4o",
            cost_usd=0.003,
        )
        image_response = ImageGenerationResponse(
            image_urls=["https://oai.example.com/slide.jpg"],
            model="gpt-image-1",
            cost_usd=0.04,
        )
        upload_result = UploadResult(
            url="https://cdn.example.com/slide.jpg",
            key="slide.jpg",
            size_bytes=100000,
        )

        ctx = AgentContext(brief=carousel_brief, brand=brand, variant=variant)

        with patch("apps.agents.carousel_agent.get_text_provider") as mock_text, \
             patch("apps.agents.carousel_agent.get_image_provider") as mock_img, \
             patch("apps.agents.carousel_agent.get_storage_provider") as mock_storage:
            mock_text.return_value = AsyncMock(generate=AsyncMock(return_value=structure_response))
            mock_img.return_value = AsyncMock(generate=AsyncMock(return_value=image_response))
            mock_storage.return_value = AsyncMock(upload_from_url=AsyncMock(return_value=upload_result))

            result = await agent.execute(ctx)

        assert result.success is True
        assert result.data["num_slides"] == 3
        assert await Asset.objects.filter(variant=variant).acount() == 3


# ── VideoAgent ────────────────────────────────────────────────


class TestVideoAgent:
    @pytest.fixture
    def agent(self):
        return VideoAgent()

    @pytest.mark.asyncio
    async def test_build_prompt(self, agent, reel_brief, brand):
        reel_brief.enriched_brief = {"tema": "Git errors", "angulo": "Tutorial"}
        await reel_brief.asave()
        ctx = AgentContext(brief=reel_brief, brand=brand)
        system, user = await agent.build_prompt(ctx)
        assert "HOOK" in system
        assert "DESARROLLO" in system
        assert "30-60" in user

    @pytest.mark.asyncio
    async def test_execute_returns_script(self, agent, reel_brief, brand):
        reel_brief.enriched_brief = {"tema": "Git", "hooks": ["Stop doing this"]}
        await reel_brief.asave()

        script = {
            "title": "3 errores con Git",
            "hook": {"text": "Stop doing this", "visual": "Screen", "duration_seconds": 3},
            "scenes": [{"scene_number": 1, "text": "Error 1", "visual": "Terminal", "duration_seconds": 5, "transition": "corte"}],
            "cta": {"text": "Follow for more", "visual": "Logo"},
            "music_mood": "energetic",
            "total_duration_seconds": 30,
            "visual_style": "modern",
        }

        mock_response = TextGenerationResponse(
            text=json.dumps(script),
            model="gpt-4o",
            cost_usd=0.005,
        )
        ctx = AgentContext(brief=reel_brief, brand=brand)

        with patch("apps.agents.video_agent.get_text_provider") as mock_get:
            mock_get.return_value = AsyncMock(generate=AsyncMock(return_value=mock_response))
            result = await agent.execute(ctx)

        assert result.success is True
        assert result.data["script"]["title"] == "3 errores con Git"
        assert result.data["rendering_pending"] is True


# ── Orchestrator ──────────────────────────────────────────────


class TestContentOrchestrator:
    def test_build_summary(self):
        orch = ContentOrchestrator()
        results = {
            "brief_enricher": AgentResult(success=True, cost_usd=0.01, duration_seconds=2),
            "copy": AgentResult(success=True, cost_usd=0.02, duration_seconds=3),
            "image": AgentResult(success=True, cost_usd=0.05, duration_seconds=10),
        }
        summary = orch._build_summary(results)
        assert summary["success"] is True
        assert summary["total_cost_usd"] == pytest.approx(0.08, abs=0.001)
        assert summary["total_duration_seconds"] == pytest.approx(15, abs=0.1)
        assert len(summary["agents"]) == 3
        assert summary["errors"] == {}

    def test_build_summary_with_failures(self):
        orch = ContentOrchestrator()
        results = {
            "brief_enricher": AgentResult(success=True, cost_usd=0.01),
            "image": AgentResult(success=False, error="timeout", cost_usd=0),
        }
        summary = orch._build_summary(results)
        assert summary["success"] is False
        assert "image" in summary["errors"]

    @pytest.mark.asyncio
    async def test_mark_failed(self, brief, brand):
        orch = ContentOrchestrator()
        await orch._mark_failed(brief, "Something broke")
        await brief.arefresh_from_db()
        assert brief.status == ContentBrief.Status.FAILED
        assert "Something broke" in brief.error_message

    @pytest.mark.asyncio
    async def test_generate_content_post_pipeline(self, brief, brand):
        """Test full orchestration for a POST brief with all agents mocked."""
        enricher_result = AgentResult(
            success=True,
            data={"tema": "test", "angulo": "angle"},
            cost_usd=0.001,
        )
        copy_result = AgentResult(
            success=True,
            data={"caption": "Test caption", "alt_text": "Alt"},
            cost_usd=0.001,
        )
        image_result = AgentResult(
            success=True,
            data={"images": [{"url": "https://cdn.com/img.jpg"}], "num_images": 1},
            cost_usd=0.04,
        )
        hashtag_result = AgentResult(
            success=True,
            data={"hashtags": ["#test"]},
            cost_usd=0.001,
        )

        orch = ContentOrchestrator()

        with patch.object(orch.brief_enricher, "execute", new_callable=AsyncMock, return_value=enricher_result), \
             patch.object(orch.copy_agent, "execute", new_callable=AsyncMock, return_value=copy_result), \
             patch.object(orch.image_agent, "execute", new_callable=AsyncMock, return_value=image_result), \
             patch.object(orch.hashtag_agent, "execute", new_callable=AsyncMock, return_value=hashtag_result):
            summary = await orch.generate_content(brief)

        assert summary["success"] is True
        assert summary["total_cost_usd"] > 0

        await brief.arefresh_from_db()
        assert brief.status == ContentBrief.Status.REVIEW
        assert await ContentVariant.objects.filter(brief=brief).aexists()

    @pytest.mark.asyncio
    async def test_generate_content_enricher_failure_stops_pipeline(self, brief, brand):
        enricher_result = AgentResult(success=False, error="API down")

        orch = ContentOrchestrator()

        with patch.object(orch.brief_enricher, "execute", new_callable=AsyncMock, return_value=enricher_result):
            summary = await orch.generate_content(brief)

        assert summary["success"] is False
        await brief.arefresh_from_db()
        assert brief.status == ContentBrief.Status.FAILED


# ── Prompts ───────────────────────────────────────────────────


class TestPrompts:
    def test_carousel_prompt(self, enriched_brief, brand):
        from apps.agents.prompts.carousel_prompt import get_system_prompt

        ctx = AgentContext(brief=enriched_brief, brand=brand)
        prompt = get_system_prompt(ctx)
        assert "PORTADA" in prompt
        assert "PROBLEMA" in prompt
        assert "CTA" in prompt
        assert brand.color_primary in prompt
        assert "Saraga" in prompt

    def test_video_prompt(self, enriched_brief, brand):
        from apps.agents.prompts.video_prompt import get_system_prompt

        ctx = AgentContext(brief=enriched_brief, brand=brand)
        prompt = get_system_prompt(ctx)
        assert "HOOK" in prompt
        assert "DESARROLLO" in prompt
        assert "30-60" in prompt
        assert "Saraga" in prompt
