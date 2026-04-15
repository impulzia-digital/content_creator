"""
CopyAgent — Genera captions, hooks y CTAs para Instagram.

Input:  enriched_brief + brand context
Output: caption, alt_text
"""

from __future__ import annotations

import json
from typing import Any

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.content.models import AgentRun
from apps.integrations.base import TextGenerationRequest


class CopyAgent(BaseAgent):
    agent_type = AgentRun.AgentType.COPY

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        brief_data = context.brief.enriched_brief or {}

        system = f"""Eres un copywriter experto en Instagram para la siguiente marca:

{context.brand_briefing}

REGLAS:
- Captions de máximo 2200 caracteres (límite de Instagram).
- Abre con un hook potente en la primera línea (antes del "...más").
- Usa line breaks para legibilidad.
- CTA claro al final.
- No uses emojis excesivos, máximo 3-5 por caption.
- Tono coherente con la marca.
- Responde SOLO en JSON válido.
"""

        user = f"""BRIEF:
Tema: {brief_data.get('tema', context.brief.title)}
Ángulo: {brief_data.get('angulo', '')}
Objetivo: {brief_data.get('objetivo', '')}
Puntos clave: {json.dumps(brief_data.get('puntos_clave', []), ensure_ascii=False)}
CTA sugerido: {brief_data.get('cta', '')}
Tono específico: {brief_data.get('tono_especifico', '')}
Tipo: {context.brief.get_content_type_display()}

Genera:
{{
    "caption": "el caption completo para Instagram",
    "alt_text": "texto alternativo descriptivo para accesibilidad (max 100 chars)",
    "hook_line": "la primera línea del caption (el hook)"
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
                temperature=0.8,
                response_format="json_object",
            )
        )

        data = await self.parse_output(response.text, context)

        # Guardar en la variante si existe
        if context.variant:
            context.variant.caption = data.get("caption", "")
            context.variant.alt_text = data.get("alt_text", "")
            await context.variant.asave(update_fields=["caption", "alt_text"])

        return AgentResult(
            success=True,
            data=data,
            cost_usd=response.cost_usd,
            provider=generation_config.provider,
            model=response.model,
        )
