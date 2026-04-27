"""
CarouselAgent — Genera carruseles multi-slide para Instagram.

Basado en la estructura Saraga Marketing:
  Slide 1: Portada (hook)
  Slide 2: Problema
  Slide 3: Promesa
  Slides 4-5: Contenido/valor
  Slide 6: Profundidad/reflexión
  Slide 7: CTA

Input:  enriched_brief + brand context
Output: estructura de slides + imágenes generadas
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.agents.prompts import carousel_prompt
from apps.assets.models import Asset
from apps.content.models import AgentRun
from apps.integrations.base import ImageGenerationRequest, TextGenerationRequest
from apps.integrations.registry import get_storage_provider


class CarouselAgent(BaseAgent):
    agent_type = AgentRun.AgentType.CAROUSEL

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        brief_data = context.brief.enriched_brief or {}
        num_slides = context.brief.num_slides or 7

        system = carousel_prompt.get_system_prompt(context)

        user = f"""BRIEF DEL CARRUSEL:
Tema: {brief_data.get('tema', context.brief.title)}
Ángulo: {brief_data.get('angulo', '')}
Objetivo: {brief_data.get('objetivo', '')}
Puntos clave: {json.dumps(brief_data.get('puntos_clave', []), ensure_ascii=False)}
CTA: {brief_data.get('cta', '')}
Número de slides: {num_slides}
Audiencia: {brief_data.get('audiencia_objetivo', context.brand.target_audience)}

Genera la estructura del carrusel en JSON:
{{
    "slides": [
        {{
            "slide_number": 1,
            "slide_type": "portada|problema|promesa|contenido|profundidad|cta",
            "headline": "título principal del slide",
            "body": "texto del cuerpo (2-3 líneas máx)",
            "visual_description": "descripción de la imagen/fondo para este slide",
            "design_notes": "notas de diseño: colores, layout, elementos"
        }}
    ],
    "visual_style": "estilo visual general del carrusel",
    "color_scheme": "esquema de colores usado"
}}"""

        return system, user

    async def parse_output(self, raw_output: Any, context: AgentContext) -> dict:
        if isinstance(raw_output, str):
            return json.loads(raw_output)
        return raw_output

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        text_provider, text_config = self.resolve_text_generation(context)
        image_provider, image_config = self.resolve_image_generation(context)
        storage = get_storage_provider()

        # Paso 1: Generar estructura del carrusel
        system, user = await self.build_prompt(context)
        structure_response = await text_provider.generate(
            TextGenerationRequest(
                system_prompt=system,
                user_prompt=user,
                model=text_config.model,
                temperature=0.7,
                max_tokens=3000,
                response_format="json_object",
            )
        )
        carousel_data = await self.parse_output(structure_response.text, context)
        slides = carousel_data.get("slides", [])
        image_width, image_height = self.resolve_image_dimensions(context)

        # Paso 2: Generar imagen para cada slide
        total_cost = structure_response.cost_usd
        assets_created = []

        for slide in slides:
            # Construir prompt visual por slide
            visual_prompt = (
                f"{slide.get('visual_description', '')}. "
                f"Text overlay: '{slide.get('headline', '')}'. "
                f"Style: {carousel_data.get('visual_style', 'clean, modern, branded')}. "
                f"Brand colors: {context.brand.color_primary} {context.brand.color_secondary}. "
                f"Instagram carousel slide, {context.brief.aspect_ratio} aspect ratio, high quality."
            )

            image_response = await image_provider.generate(
                ImageGenerationRequest(
                    prompt=visual_prompt,
                    width=image_width,
                    height=image_height,
                    model=image_config.model,
                )
            )
            total_cost += image_response.cost_usd
            rendered_width = image_response.width or image_width
            rendered_height = image_response.height or image_height
            content_type = image_response.content_type or "image/jpeg"
            images_created_for_slide = 0

            # Subir a S3
            for url in image_response.image_urls:
                key = (
                    f"brands/{context.brand.slug}/content/{context.brief.id}/"
                    f"carousel_{slide['slide_number']:02d}_{uuid.uuid4().hex[:8]}.jpg"
                )
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
                        width=rendered_width,
                        height=rendered_height,
                        position=slide["slide_number"] - 1,
                        generation_prompt=visual_prompt,
                        generation_params={
                            **slide,
                            "_text_generation": text_config.as_dict(),
                            "_image_generation": image_config.as_dict(),
                        },
                    )
                    await asset.asave()
                    assets_created.append({
                        "slide": slide["slide_number"],
                        "url": upload.url,
                        "key": upload.key,
                    })
                    images_created_for_slide += 1

            for image_data in image_response.image_bytes:
                key = (
                    f"brands/{context.brand.slug}/content/{context.brief.id}/"
                    f"carousel_{slide['slide_number']:02d}_{uuid.uuid4().hex[:8]}.jpg"
                )
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
                        width=rendered_width,
                        height=rendered_height,
                        position=slide["slide_number"] - 1,
                        generation_prompt=visual_prompt,
                        generation_params={
                            **slide,
                            "_text_generation": text_config.as_dict(),
                            "_image_generation": image_config.as_dict(),
                        },
                    )
                    await asset.asave()
                    assets_created.append({
                        "slide": slide["slide_number"],
                        "url": upload.url,
                        "key": upload.key,
                    })
                    images_created_for_slide += 1

            if images_created_for_slide == 0:
                raise ValueError(
                    f"El proveedor de imagen no devolvio imagenes para el slide {slide['slide_number']}"
                )

        return AgentResult(
            success=True,
            data={
                "carousel_structure": carousel_data,
                "assets": assets_created,
                "num_slides": len(slides),
            },
            cost_usd=total_cost,
            provider=image_config.provider,
            model=structure_response.model,
        )
