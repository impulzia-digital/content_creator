"""
VideoAgent — Genera scripts y coordina la creación de reels.

Basado en la estructura Saraga Marketing:
  Hook (2-3 seg) → Desarrollo (valor) → Cierre + CTA

Input:  enriched_brief + brand context
Output: script estructurado + video renderizado
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.agents.prompts import video_prompt
from apps.assets.models import Asset
from apps.content.models import AgentRun
from apps.integrations.base import TextGenerationRequest
from apps.integrations.registry import get_text_provider


class VideoAgent(BaseAgent):
    agent_type = AgentRun.AgentType.VIDEO

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        brief_data = context.brief.enriched_brief or {}

        system = video_prompt.get_system_prompt(context)

        user = f"""BRIEF DEL REEL:
Tema: {brief_data.get('tema', context.brief.title)}
Ángulo: {brief_data.get('angulo', '')}
Objetivo: {brief_data.get('objetivo', '')}
Puntos clave: {json.dumps(brief_data.get('puntos_clave', []), ensure_ascii=False)}
Hooks sugeridos: {json.dumps(brief_data.get('hooks', []), ensure_ascii=False)}
CTA: {brief_data.get('cta', '')}
Duración objetivo: 30-60 segundos

Genera el script del reel en JSON:
{{
    "title": "título del reel",
    "hook": {{
        "text": "texto del hook (2-3 seg, primera frase que se ve)",
        "visual": "descripción de lo que se ve",
        "duration_seconds": 3
    }},
    "scenes": [
        {{
            "scene_number": 1,
            "text": "narración o texto en pantalla",
            "visual": "descripción visual",
            "duration_seconds": 5,
            "transition": "corte|fade|slide"
        }}
    ],
    "cta": {{
        "text": "call to action final",
        "visual": "descripción visual del cierre"
    }},
    "music_mood": "mood de la música de fondo",
    "total_duration_seconds": 30,
    "visual_style": "estilo visual general"
}}"""

        return system, user

    async def parse_output(self, raw_output: Any, context: AgentContext) -> dict:
        if isinstance(raw_output, str):
            return json.loads(raw_output)
        return raw_output

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        text_provider = get_text_provider()

        # Paso 1: Generar script del video
        system, user = await self.build_prompt(context)
        script_response = await text_provider.generate(
            TextGenerationRequest(
                system_prompt=system,
                user_prompt=user,
                model="gpt-4o",
                temperature=0.7,
                max_tokens=3000,
                response_format="json_object",
            )
        )
        script_data = await self.parse_output(script_response.text, context)

        # Paso 2: Video rendering se hace en tasks/publish pipeline
        # Aquí solo generamos el script y lo guardamos
        # El rendering real depende del VIDEO_PROVIDER configurado

        return AgentResult(
            success=True,
            data={
                "script": script_data,
                "rendering_pending": True,
                "note": "Script generado. Rendering se ejecuta como tarea separada.",
            },
            cost_usd=script_response.cost_usd,
            provider="openai",
            model=script_response.model,
        )
