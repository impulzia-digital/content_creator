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

from django.conf import settings

from apps.agents.base import AgentContext, AgentResult, BaseAgent
from apps.agents.prompts import video_prompt
from apps.assets.models import Asset
from apps.content.models import AgentRun
from apps.integrations.base import TextGenerationRequest, VideoGenerationRequest
from apps.integrations.registry import get_storage_provider


ASPECT_RATIOS = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


class VideoAgent(BaseAgent):
    agent_type = AgentRun.AgentType.VIDEO

    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        brief_data = context.brief.enriched_brief or {}
        video_config = ((context.extra.get("generation_config") or {}).get("video") or {})
        target_duration = "4-8 segundos" if video_config.get("provider") == "veo" else "30-60 segundos"

        system = video_prompt.get_system_prompt(context)

        user = f"""BRIEF DEL REEL:
Tema: {brief_data.get('tema', context.brief.title)}
Ángulo: {brief_data.get('angulo', '')}
Objetivo: {brief_data.get('objetivo', '')}
Puntos clave: {json.dumps(brief_data.get('puntos_clave', []), ensure_ascii=False)}
Hooks sugeridos: {json.dumps(brief_data.get('hooks', []), ensure_ascii=False)}
CTA: {brief_data.get('cta', '')}
Duración objetivo: {target_duration}

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
        text_provider, generation_config = self.resolve_text_generation(context)
        video_provider, video_config = self.resolve_video_generation(context)
        storage = get_storage_provider()

        # Paso 1: Generar script del video
        system, user = await self.build_prompt(context)
        script_response = await text_provider.generate(
            TextGenerationRequest(
                system_prompt=system,
                user_prompt=user,
                model=generation_config.model,
                temperature=0.7,
                max_tokens=3000,
                response_format="json_object",
            )
        )
        script_data = await self.parse_output(script_response.text, context)
        width, height = ASPECT_RATIOS.get(context.brief.aspect_ratio, (1080, 1920))

        # Paso 2: Renderizar y persistir assets de video
        video_request = self._build_video_request(
            context=context,
            script_data=script_data,
            video_model=video_config.model,
            width=width,
            height=height,
        )
        video_response = await video_provider.generate(video_request)
        assets = await self._persist_assets(
            context=context,
            storage=storage,
            script_data=script_data,
            text_generation_config=generation_config.as_dict(),
            video_generation_config=video_config.as_dict(),
            video_request=video_request,
            video_response=video_response,
            width=width,
            height=height,
        )

        total_cost = script_response.cost_usd + video_response.cost_usd

        return AgentResult(
            success=True,
            data={
                "script": script_data,
                "rendered": True,
                "assets": assets,
            },
            cost_usd=total_cost,
            provider=video_config.provider,
            model=video_response.model,
        )

    def _build_video_request(
        self,
        *,
        context: AgentContext,
        script_data: dict,
        video_model: str,
        width: int,
        height: int,
    ) -> VideoGenerationRequest:
        video_config = ((context.extra.get("generation_config") or {}).get("video") or {})
        provider = video_config.get("provider", "")
        duration_seconds = float(script_data.get("total_duration_seconds") or _calculate_script_duration(script_data) or 8.0)

        if provider == "veo":
            return VideoGenerationRequest(
                prompt=_build_veo_prompt(context, script_data),
                negative_prompt="blurry, distorted anatomy, unreadable text, watermark, logo overlay, low quality",
                model=video_model,
                duration_seconds=duration_seconds,
                width=width,
                height=height,
            )

        template_id = ""
        if video_model == "creatomate-template":
            template_id = getattr(settings, "CREATOMATE_REEL_TEMPLATE_ID", "").strip()
        elif video_model and video_model != "creatomate-renderscript":
            template_id = video_model

        if template_id:
            return VideoGenerationRequest(
                template_id=template_id,
                template_params=_build_creatomate_template_params(context, script_data),
                model=video_model,
                duration_seconds=duration_seconds,
                width=width,
                height=height,
            )

        return VideoGenerationRequest(
            render_spec=_build_creatomate_render_spec(context, script_data, width, height),
            model=video_model or getattr(settings, "CREATOMATE_VIDEO_MODEL", "creatomate-renderscript"),
            duration_seconds=duration_seconds,
            width=width,
            height=height,
        )

    async def _persist_assets(
        self,
        *,
        context: AgentContext,
        storage,
        script_data: dict,
        text_generation_config: dict,
        video_generation_config: dict,
        video_request: VideoGenerationRequest,
        video_response,
        width: int,
        height: int,
    ) -> list[dict[str, str]]:
        assets: list[dict[str, str]] = []
        if not context.variant:
            return assets

        video_content_type = video_response.content_type or "video/mp4"
        video_key = _build_asset_key(context, video_content_type)
        video_upload = await _upload_media(
            storage=storage,
            source_url=video_response.video_url,
            data=video_response.video_bytes,
            key=video_key,
            content_type=video_content_type,
        )
        video_asset = Asset(
            variant=context.variant,
            asset_type=Asset.AssetType.VIDEO,
            source=_resolve_asset_source(video_generation_config.get("provider", "")),
            file_url=video_upload.url,
            file_key=video_upload.key,
            file_size_bytes=video_upload.size_bytes,
            mime_type=video_content_type,
            width=width,
            height=height,
            duration_seconds=video_response.duration_seconds or video_request.duration_seconds,
            position=0,
            generation_prompt=video_request.prompt,
            generation_params={
                "script": script_data,
                "template_id": video_request.template_id,
                "template_params": video_request.template_params,
                "render_spec": video_request.render_spec,
                "_text_generation": text_generation_config,
                "_video_generation": video_generation_config,
            },
        )
        await video_asset.asave()
        assets.append({"asset_type": Asset.AssetType.VIDEO, "url": video_upload.url, "key": video_upload.key})

        thumbnail_ref = video_response.thumbnail_url or video_response.thumbnail_bytes
        if thumbnail_ref:
            thumbnail_content_type = video_response.thumbnail_content_type or "image/jpeg"
            thumbnail_key = _build_asset_key(context, thumbnail_content_type)
            thumbnail_upload = await _upload_media(
                storage=storage,
                source_url=video_response.thumbnail_url,
                data=video_response.thumbnail_bytes,
                key=thumbnail_key,
                content_type=thumbnail_content_type,
            )
            thumbnail_asset = Asset(
                variant=context.variant,
                asset_type=Asset.AssetType.THUMBNAIL,
                source=_resolve_asset_source(video_generation_config.get("provider", "")),
                file_url=thumbnail_upload.url,
                file_key=thumbnail_upload.key,
                file_size_bytes=thumbnail_upload.size_bytes,
                mime_type=thumbnail_content_type,
                width=width,
                height=height,
                position=0,
                generation_prompt=video_request.prompt,
                generation_params={
                    "script": script_data,
                    "_video_generation": video_generation_config,
                },
            )
            await thumbnail_asset.asave()
            assets.append({"asset_type": Asset.AssetType.THUMBNAIL, "url": thumbnail_upload.url, "key": thumbnail_upload.key})

        return assets


def _build_veo_prompt(context: AgentContext, script_data: dict) -> str:
    sections = _script_sections(script_data)
    top_sections = sections[:3]
    section_lines = [
        f"Scene {index + 1}: {section['text']} Visual: {section['visual']}"
        for index, section in enumerate(top_sections)
    ]
    return (
        "Create a vertical 9:16 cinematic social video for Instagram. "
        f"Brand tone: {context.brand.tone_description or 'bold and modern'}. "
        f"Visual style: {script_data.get('visual_style', 'modern cinematic')}. "
        f"Music mood: {script_data.get('music_mood', 'energetic')}. "
        f"Primary color palette: {context.brand.color_primary}, {context.brand.color_secondary}, {context.brand.color_accent}. "
        + " ".join(section_lines)
        + " No subtitles, no watermarks, no interface chrome, no text overlays."
    )


def _build_creatomate_template_params(context: AgentContext, script_data: dict) -> dict[str, Any]:
    params: dict[str, Any] = {
        "Title": script_data.get("title", context.brief.title),
        "Hook": (script_data.get("hook") or {}).get("text", ""),
        "CTA": (script_data.get("cta") or {}).get("text", ""),
        "Brand-Primary": context.brand.color_primary,
        "Brand-Secondary": context.brand.color_secondary,
        "Brand-Accent": context.brand.color_accent,
    }
    for index, section in enumerate(_script_sections(script_data), start=1):
        params[f"Scene-{index}-Text"] = section["text"]
        params[f"Scene-{index}-Visual"] = section["visual"]
        params[f"Scene-{index}-Duration"] = section["duration_seconds"]
    return params


def _build_creatomate_render_spec(context: AgentContext, script_data: dict, width: int, height: int) -> dict[str, Any]:
    sections = _script_sections(script_data)
    total_duration = round(sum(section["duration_seconds"] for section in sections), 2) or 8.0
    palette = [
        context.brand.color_primary or "#0F172A",
        context.brand.color_secondary or "#1D4ED8",
        context.brand.color_accent or "#F59E0B",
    ]
    elements: list[dict[str, Any]] = []
    offset = 0.0

    for index, section in enumerate(sections):
        scene_elements = [
            {
                "type": "text",
                "track": 1,
                "time": 0,
                "x": "8%",
                "y": "16%",
                "width": "84%",
                "height": "24%",
                "fill_color": "rgba(255,255,255,1)",
                "text": section["text"],
                "font_family": "Montserrat",
                "font_weight": "800",
                "font_size": "7.2 vmin",
                "line_height": "118%",
                "background_color": "rgba(0,0,0,0.18)",
                "background_x_padding": "10%",
                "background_y_padding": "8%",
                "background_border_radius": "10%",
                "animations": [
                    {"time": 0, "duration": 0.45, "type": "fade", "easing": "quadratic-out"}
                ],
            },
            {
                "type": "text",
                "track": 2,
                "time": 0.25,
                "x": "8%",
                "y": "73%",
                "width": "84%",
                "height": "12%",
                "fill_color": "rgba(255,255,255,0.92)",
                "text": section["visual"],
                "font_family": "Inter",
                "font_weight": "500",
                "font_size": "3.1 vmin",
                "line_height": "130%",
                "opacity": "82%",
                "background_color": "rgba(15,23,42,0.35)",
                "background_x_padding": "6%",
                "background_y_padding": "5%",
                "background_border_radius": "8%",
            },
            {
                "type": "text",
                "track": 3,
                "time": 0,
                "x": "8%",
                "y": "92%",
                "width": "40%",
                "height": "6%",
                "fill_color": "rgba(255,255,255,0.96)",
                "text": context.brand.name,
                "font_family": "Montserrat",
                "font_weight": "700",
                "font_size": "2.6 vmin",
                "background_color": "rgba(0,0,0,0.25)",
                "background_x_padding": "7%",
                "background_y_padding": "7%",
                "background_border_radius": "999%",
            },
        ]
        elements.append(
            {
                "name": f"Scene-{index + 1}",
                "type": "composition",
                "track": 1,
                "time": round(offset, 2),
                "duration": section["duration_seconds"],
                "fill_color": palette[index % len(palette)],
                "animations": _scene_transition(index),
                "elements": scene_elements,
            }
        )
        offset += section["duration_seconds"]

    return {
        "output_format": "mp4",
        "width": width,
        "height": height,
        "duration": total_duration,
        "elements": elements,
    }


def _scene_transition(index: int) -> list[dict[str, Any]]:
    if index == 0:
        return []
    return [
        {
            "time": 0,
            "duration": 0.35,
            "transition": True,
            "type": "fade",
        }
    ]


def _script_sections(script_data: dict) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    hook = script_data.get("hook") or {}
    if hook.get("text"):
        sections.append(
            {
                "text": hook.get("text", ""),
                "visual": hook.get("visual", ""),
                "duration_seconds": float(hook.get("duration_seconds") or 3),
            }
        )

    for scene in script_data.get("scenes", []) or []:
        if not scene.get("text"):
            continue
        sections.append(
            {
                "text": scene.get("text", ""),
                "visual": scene.get("visual", ""),
                "duration_seconds": float(scene.get("duration_seconds") or 4),
            }
        )

    cta = script_data.get("cta") or {}
    if cta.get("text"):
        sections.append(
            {
                "text": cta.get("text", ""),
                "visual": cta.get("visual", ""),
                "duration_seconds": 3.0,
            }
        )

    return sections or [{"text": context_title(script_data), "visual": "", "duration_seconds": 8.0}]


def context_title(script_data: dict) -> str:
    return script_data.get("title") or "Instagram reel"


def _calculate_script_duration(script_data: dict) -> float:
    return sum(section["duration_seconds"] for section in _script_sections(script_data))


def _build_asset_key(context: AgentContext, content_type: str) -> str:
    extension = _extension_for_content_type(content_type)
    return f"brands/{context.brand.slug}/content/{context.brief.id}/{uuid.uuid4()}.{extension}"


def _extension_for_content_type(content_type: str) -> str:
    normalized = content_type.lower()
    if normalized == "video/mp4":
        return "mp4"
    if normalized == "image/png":
        return "png"
    if normalized == "image/webp":
        return "webp"
    return "jpg"


def _resolve_asset_source(provider: str) -> str:
    return Asset.Source.TEMPLATE if provider == "creatomate" else Asset.Source.GENERATED


async def _upload_media(*, storage, source_url: str, data: bytes | None, key: str, content_type: str):
    if data is not None:
        return await storage.upload_bytes(data, key, content_type)
    if source_url:
        return await storage.upload_from_url(source_url, key, content_type)
    raise ValueError("El provider de video no devolvió bytes ni URL para subir")
