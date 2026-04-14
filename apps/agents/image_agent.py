"""
ImageAgent — Genera imágenes para posts de Instagram.

Input:  enriched_brief + brand context
Output: image URLs generadas, subidas a S3
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.assets.models import Asset
from apps.content.models import AgentRun
from apps.integrations.base import ImageGenerationRequest, TextGenerationRequest
from apps.integrations.registry import get_image_provider, get_storage_provider, get_text_provider


# Aspect ratio → dimensiones
ASPECT_RATIOS = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


class ImageAgent(BaseAgent):
    agent_type = AgentRun.AgentType.IMAGE

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        brief_data = context.brief.enriched_brief or {}

        system = f"""Eres un director de arte especializado en content visual para Instagram.
Tu trabajo es crear prompts de generación de imagen que produzcan visuals de alta calidad.

MARCA:
{context.brand_briefing}

ESTILO PREFERIDO: {context.brand.preferred_image_style or 'moderno, limpio, profesional'}
"""

        user = f"""BRIEF VISUAL:
Tema: {brief_data.get('tema', context.brief.title)}
Ángulo: {brief_data.get('angulo', '')}
Referencia visual: {brief_data.get('referencia_visual', '')}
Tipo: {context.brief.get_content_type_display()}
Aspect ratio: {context.brief.aspect_ratio}
Paleta: Principal={context.brand.color_primary}, Secundario={context.brand.color_secondary}, Acento={context.brand.color_accent}

Genera un prompt de imagen detallado en JSON:
{{
    "image_prompt": "prompt detallado para generación de imagen, en inglés, estilo fotográfico/ilustrativo",
    "negative_prompt": "qué evitar en la imagen",
    "style_notes": "notas sobre el estilo visual"
}}"""

        return system, user

    async def parse_output(self, raw_output: Any, context: AgentContext) -> dict:
        if isinstance(raw_output, str):
            return json.loads(raw_output)
        return raw_output

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        text_provider = get_text_provider()
        image_provider = get_image_provider()
        storage = get_storage_provider()

        # Paso 1: Generar prompt visual con LLM
        system, user = await self.build_prompt(context)
        prompt_response = await text_provider.generate(
            TextGenerationRequest(
                system_prompt=system,
                user_prompt=user,
                model="gpt-4o-mini",
                temperature=0.7,
                response_format="json_object",
            )
        )
        prompt_data = await self.parse_output(prompt_response.text, context)

        # Paso 2: Generar imagen
        w, h = ASPECT_RATIOS.get(context.brief.aspect_ratio, (1080, 1350))
        image_response = await image_provider.generate(
            ImageGenerationRequest(
                prompt=prompt_data["image_prompt"],
                negative_prompt=prompt_data.get("negative_prompt", ""),
                width=w,
                height=h,
                style=context.brand.preferred_image_style,
            )
        )
        image_width = image_response.width or w
        image_height = image_response.height or h
        content_type = image_response.content_type or "image/jpeg"

        # Paso 3: Subir a S3 y crear Assets
        assets_created = []
        for i, url in enumerate(image_response.image_urls):
            key = f"brands/{context.brand.slug}/content/{context.brief.id}/{uuid.uuid4()}.jpg"
            upload = await storage.upload_from_url(url, key, content_type)

            if context.variant:
                asset = Asset(
                    variant=context.variant,
                    asset_type=Asset.AssetType.IMAGE,
                    source=Asset.Source.GENERATED,
                    file_url=upload.url,
                    file_key=upload.key,
                    file_size_bytes=upload.size_bytes,
                    mime_type=content_type,
                    width=image_width,
                    height=image_height,
                    position=i,
                    generation_prompt=prompt_data["image_prompt"],
                    generation_params=prompt_data,
                )
                await asset.asave()
                assets_created.append({"url": upload.url, "key": upload.key})

        for i, image_data in enumerate(image_response.image_bytes, start=len(assets_created)):
            key = f"brands/{context.brand.slug}/content/{context.brief.id}/{uuid.uuid4()}.jpg"
            upload = await storage.upload_bytes(image_data, key, content_type)

            if context.variant:
                asset = Asset(
                    variant=context.variant,
                    asset_type=Asset.AssetType.IMAGE,
                    source=Asset.Source.GENERATED,
                    file_url=upload.url,
                    file_key=upload.key,
                    file_size_bytes=upload.size_bytes,
                    mime_type=content_type,
                    width=image_width,
                    height=image_height,
                    position=i,
                    generation_prompt=prompt_data["image_prompt"],
                    generation_params=prompt_data,
                )
                await asset.asave()
                assets_created.append({"url": upload.url, "key": upload.key})

        if not assets_created:
            raise ValueError("El proveedor de imagen no devolvio imagenes utilizables")

        total_cost = prompt_response.cost_usd + image_response.cost_usd

        return AgentResult(
            success=True,
            data={
                "prompt_data": prompt_data,
                "images": assets_created,
                "num_images": len(assets_created),
            },
            cost_usd=total_cost,
            provider="openai",
            model=image_response.model,
        )
