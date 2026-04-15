"""
BriefEnricherAgent — Expande una idea cruda en un brief estructurado.

Input:  raw_idea (texto libre del usuario)
Output: enriched_brief (JSON con tema, ángulo, hooks, keywords, formato sugerido)
"""

from __future__ import annotations

import json
from typing import Any

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.content.models import AgentRun
from apps.integrations.base import TextGenerationRequest


class BriefEnricherAgent(BaseAgent):
    agent_type = AgentRun.AgentType.BRIEF_ENRICHER

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        system = f"""Eres un estratega de contenido para Instagram especializado en la marca descrita abajo.
Tu trabajo es tomar una idea cruda y expandirla en un brief editorial estructurado.

{context.brand_briefing}

REGLAS:
- Responde SOLO en JSON válido, sin markdown ni backticks.
- El brief debe ser accionable para un equipo de diseño y copywriting.
- Sugiere el mejor formato (post, carrusel, reel, story) según la idea.
- Si la idea es vaga, propon un ángulo específico y diferenciador.
"""

        user = f"""IDEA CRUDA:
{context.brief.raw_idea}

Tipo de contenido solicitado: {context.brief.get_content_type_display()}

Genera un brief estructurado con este JSON schema:
{{
    "tema": "tema principal",
    "angulo": "ángulo editorial específico",
    "objetivo": "qué debe lograr este contenido",
    "formato_sugerido": "post|carousel|reel|story",
    "num_slides_sugerido": 1,
    "hooks": ["hook 1", "hook 2", "hook 3"],
    "puntos_clave": ["punto 1", "punto 2", "punto 3"],
    "cta": "call to action sugerido",
    "keywords": ["keyword1", "keyword2"],
    "tono_especifico": "descripción del tono para este contenido",
    "referencia_visual": "descripción del estilo visual sugerido",
    "audiencia_objetivo": "segmento específico de la audiencia"
}}"""

        return system, user

    async def parse_output(self, raw_output: Any, context: AgentContext) -> dict:
        if isinstance(raw_output, str):
            return json.loads(raw_output)
        return raw_output

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        system, user = await self.build_prompt(context)
        provider, generation_config = self.resolve_text_generation(context)

        response = await provider.generate(
            TextGenerationRequest(
                system_prompt=system,
                user_prompt=user,
                model=generation_config.model,
                temperature=0.7,
                response_format="json_object",
            )
        )

        data = await self.parse_output(response.text, context)

        # Guardar enriched_brief en el brief
        context.brief.enriched_brief = data
        await context.brief.asave(update_fields=["enriched_brief"])

        return AgentResult(
            success=True,
            data=data,
            cost_usd=response.cost_usd,
            provider=generation_config.provider,
            model=response.model,
        )
