"""
HashtagAgent — Genera hashtags optimizados para Instagram.

Input:  enriched_brief + caption
Output: lista de hashtags (mix de alto/medio/bajo volumen)
"""

from __future__ import annotations

import json
from typing import Any

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.content.models import AgentRun
from apps.integrations.base import TextGenerationRequest
from apps.integrations.registry import get_text_provider


class HashtagAgent(BaseAgent):
    agent_type = AgentRun.AgentType.HASHTAG

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        brief_data = context.brief.enriched_brief or {}
        caption = ""
        if context.variant:
            caption = context.variant.caption

        brand_hashtags = context.brand.default_hashtags or []

        system = f"""Eres un especialista en hashtags de Instagram para la siguiente marca:

{context.brand_briefing}

REGLAS:
- Genera exactamente 20-30 hashtags.
- Mix de volúmenes: 5 altos (>500K posts), 10 medios (50K-500K), 10-15 de nicho (<50K).
- Incluye los hashtags de marca si aplican: {json.dumps(brand_hashtags, ensure_ascii=False)}
- Todos deben ser relevantes al contenido específico.
- Idioma: {context.brand.default_language}
- NO incluir hashtags prohibidos/shadowbanned.
- Responde SOLO en JSON válido.
"""

        user = f"""CONTENIDO:
Tema: {brief_data.get('tema', context.brief.title)}
Keywords: {json.dumps(brief_data.get('keywords', []), ensure_ascii=False)}
Caption: {caption[:500]}
Industria: {context.brand.industry}

Genera:
{{
    "hashtags": ["#hashtag1", "#hashtag2", "..."],
    "hashtag_groups": {{
        "brand": ["hashtags de marca"],
        "high_volume": ["hashtags de alto volumen"],
        "medium_volume": ["hashtags de medio volumen"],
        "niche": ["hashtags de nicho"]
    }}
}}"""

        return system, user

    async def parse_output(self, raw_output: Any, context: AgentContext) -> dict:
        if isinstance(raw_output, str):
            return json.loads(raw_output)
        return raw_output

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        system, user = await self.build_prompt(context)
        provider = get_text_provider()

        response = await provider.generate(
            TextGenerationRequest(
                system_prompt=system,
                user_prompt=user,
                model="gpt-4o-mini",
                temperature=0.6,
                response_format="json_object",
            )
        )

        data = await self.parse_output(response.text, context)

        # Guardar hashtags en la variante
        if context.variant:
            context.variant.hashtags = data.get("hashtags", [])
            await context.variant.asave(update_fields=["hashtags"])

        return AgentResult(
            success=True,
            data=data,
            cost_usd=response.cost_usd,
            provider="openai",
            model=response.model,
        )
