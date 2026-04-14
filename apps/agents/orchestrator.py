"""
Orquestador de sub-agentes.

Según el content_type del brief, ejecuta la cadena correcta de agentes:

POST:     BriefEnricher → CopyAgent + ImageAgent (parallel) → HashtagAgent
CAROUSEL: BriefEnricher → CarouselAgent → CopyAgent → HashtagAgent
REEL:     BriefEnricher → VideoAgent → CopyAgent → HashtagAgent
STORY:    BriefEnricher → ImageAgent → CopyAgent
"""

from __future__ import annotations

import logging

from apps.agents.base import AgentContext, AgentResult
from apps.agents.brief_enricher import BriefEnricherAgent
from apps.agents.carousel_agent import CarouselAgent
from apps.agents.copy_agent import CopyAgent
from apps.agents.hashtag_agent import HashtagAgent
from apps.agents.image_agent import ImageAgent
from apps.agents.video_agent import VideoAgent
from apps.brands.models import Brand
from apps.content.models import ContentBrief, ContentVariant

logger = logging.getLogger(__name__)


class ContentOrchestrator:
    """
    Orquesta la ejecución de sub-agentes para un brief.
    """

    def __init__(self):
        self.brief_enricher = BriefEnricherAgent()
        self.copy_agent = CopyAgent()
        self.hashtag_agent = HashtagAgent()
        self.image_agent = ImageAgent()
        self.carousel_agent = CarouselAgent()
        self.video_agent = VideoAgent()

    async def generate_content(self, brief: ContentBrief) -> dict:
        """
        Ejecuta la pipeline completa para un brief.
        Retorna un dict con resultados de cada agente.
        """
        brand = await Brand.objects.aget(pk=brief.brand_id)
        results: dict[str, AgentResult] = {}

        # Actualizar status
        brief.status = ContentBrief.Status.GENERATING
        brief.error_message = ""
        await brief.asave(update_fields=["status", "error_message"])

        try:
            # Paso 1: Enriquecer brief
            context = AgentContext(brief=brief, brand=brand)
            results["brief_enricher"] = await self.brief_enricher.execute(context)

            if not results["brief_enricher"].success:
                await self._mark_failed(brief, "Brief enrichment falló")
                return self._build_summary(results)

            # Paso 2: Crear variante
            variant, _ = await ContentVariant.objects.aget_or_create(
                brief=brief,
                version=1,
            )
            context.variant = variant

            # Paso 3: Pipeline según tipo
            content_type = brief.content_type
            if content_type == ContentBrief.ContentType.POST:
                results.update(await self._pipeline_post(context))
            elif content_type == ContentBrief.ContentType.CAROUSEL:
                results.update(await self._pipeline_carousel(context))
            elif content_type == ContentBrief.ContentType.REEL:
                results.update(await self._pipeline_reel(context))
            elif content_type == ContentBrief.ContentType.STORY:
                results.update(await self._pipeline_story(context))

            if not all(result.success for result in results.values()):
                first_error = next(
                    (result.error for result in results.values() if not result.success and result.error),
                    "La generación falló en uno o más agentes",
                )
                await self._mark_failed(brief, first_error)
                return self._build_summary(results)

            # Paso 4: Marcar como review
            brief.status = ContentBrief.Status.REVIEW
            brief.error_message = ""
            await brief.asave(update_fields=["status", "error_message"])

            # Seleccionar variante
            variant.is_selected = True
            await variant.asave(update_fields=["is_selected"])

        except Exception as exc:
            logger.exception("Orchestrator falló para brief %s: %s", brief.id, exc)
            results["orchestrator"] = AgentResult(success=False, error=str(exc))
            await self._mark_failed(brief, str(exc))

        return self._build_summary(results)

    async def _pipeline_post(self, context: AgentContext) -> dict[str, AgentResult]:
        """POST: Image + Copy (paralelo posible) → Hashtags."""
        results = {}

        # Imagen
        results["image"] = await self.image_agent.execute(context)

        # Copy
        results["copy"] = await self.copy_agent.execute(context)

        # Hashtags (después del copy, para tener el caption)
        results["hashtags"] = await self.hashtag_agent.execute(context)

        return results

    async def _pipeline_carousel(self, context: AgentContext) -> dict[str, AgentResult]:
        """CAROUSEL: Estructura + slides → Copy → Hashtags."""
        results = {}

        results["carousel"] = await self.carousel_agent.execute(context)
        results["copy"] = await self.copy_agent.execute(context)
        results["hashtags"] = await self.hashtag_agent.execute(context)

        return results

    async def _pipeline_reel(self, context: AgentContext) -> dict[str, AgentResult]:
        """REEL: Script de video → Copy → Hashtags."""
        results = {}

        results["video"] = await self.video_agent.execute(context)
        results["copy"] = await self.copy_agent.execute(context)
        results["hashtags"] = await self.hashtag_agent.execute(context)

        return results

    async def _pipeline_story(self, context: AgentContext) -> dict[str, AgentResult]:
        """STORY: Imagen → Copy (sin hashtags)."""
        results = {}

        results["image"] = await self.image_agent.execute(context)
        results["copy"] = await self.copy_agent.execute(context)

        return results

    async def _mark_failed(self, brief: ContentBrief, error: str) -> None:
        brief.status = ContentBrief.Status.FAILED
        brief.error_message = error[:2000]
        await brief.asave(update_fields=["status", "error_message"])

    def _build_summary(self, results: dict[str, AgentResult]) -> dict:
        total_cost = sum(r.cost_usd for r in results.values())
        total_time = sum(r.duration_seconds for r in results.values())
        all_success = all(r.success for r in results.values())
        errors = {k: r.error for k, r in results.items() if not r.success}

        return {
            "success": all_success,
            "total_cost_usd": total_cost,
            "total_duration_seconds": total_time,
            "agents": {k: {"success": r.success, "cost": r.cost_usd} for k, r in results.items()},
            "errors": errors,
        }
