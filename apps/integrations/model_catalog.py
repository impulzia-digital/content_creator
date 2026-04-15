"""Catálogo central de modelos IA — fuente única para UI, validación y defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal


CapabilityType = Literal["text", "image", "video"]
TierType = Literal["Potente", "Balanceado", "Eficiente"]


@dataclass(frozen=True)
class ModelEntry:
    provider: str
    capability: CapabilityType
    value: str  # Model ID que se envía al API
    label: str  # Nombre amigable para UI
    tier: TierType
    is_preview: bool = False
    is_recommended: bool = False
    description: str = ""
    api_family: str = ""  # "imagen" para Imagen 4, vacío = API estándar del provider


# ── Catálogo curado ──────────────────────────────────────────

_CATALOG: list[ModelEntry] = [
    # ── OpenAI Text ──────────────────────────────────────────
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-5.4",
        label="GPT-5.4",
        tier="Potente",
        description="Modelo flagship de OpenAI. Máxima inteligencia.",
    ),
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-5.4-mini",
        label="GPT-5.4 Mini",
        tier="Balanceado",
        is_recommended=True,
        description="Balance óptimo entre inteligencia y costo.",
    ),
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-5.4-nano",
        label="GPT-5.4 Nano",
        tier="Eficiente",
        description="Ultra-eficiente para tareas de alto volumen.",
    ),
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-4.1",
        label="GPT-4.1",
        tier="Potente",
        description="Modelo legacy de alta capacidad para compatibilidad.",
    ),
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-4o",
        label="GPT-4o",
        tier="Balanceado",
        description="Omnimodel estable con amplia compatibilidad.",
    ),
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-4.1-mini",
        label="GPT-4.1 Mini",
        tier="Balanceado",
        description="Versión ligera de GPT-4.1 para workloads mixtos.",
    ),
    ModelEntry(
        provider="openai",
        capability="text",
        value="gpt-4o-mini",
        label="GPT-4o Mini",
        tier="Eficiente",
        description="Compatibilidad legacy de bajo costo y alta velocidad.",
    ),
    # ── Gemini Text ──────────────────────────────────────────
    ModelEntry(
        provider="gemini",
        capability="text",
        value="gemini-3.1-pro-preview",
        label="Gemini 3.1 Pro",
        tier="Potente",
        is_preview=True,
        description="Máxima capacidad de razonamiento de Google.",
    ),
    ModelEntry(
        provider="gemini",
        capability="text",
        value="gemini-2.5-pro",
        label="Gemini 2.5 Pro",
        tier="Potente",
        description="Razonamiento avanzado, estable.",
    ),
    ModelEntry(
        provider="gemini",
        capability="text",
        value="gemini-3-flash-preview",
        label="Gemini 3 Flash",
        tier="Balanceado",
        is_preview=True,
        description="Rápido y capaz, última generación.",
    ),
    ModelEntry(
        provider="gemini",
        capability="text",
        value="gemini-2.5-flash",
        label="Gemini 2.5 Flash",
        tier="Balanceado",
        is_recommended=True,
        description="Balance óptimo entre velocidad y calidad.",
    ),
    ModelEntry(
        provider="gemini",
        capability="text",
        value="gemini-3.1-flash-lite-preview",
        label="Gemini 3.1 Flash Lite",
        tier="Eficiente",
        is_preview=True,
        description="Ultra-eficiente, nueva generación.",
    ),
    ModelEntry(
        provider="gemini",
        capability="text",
        value="gemini-2.5-flash-lite",
        label="Gemini 2.5 Flash Lite",
        tier="Eficiente",
        description="Máxima eficiencia en costo por token.",
    ),
    # ── OpenAI Image ─────────────────────────────────────────
    ModelEntry(
        provider="openai",
        capability="image",
        value="gpt-image-1.5",
        label="GPT Image 1.5",
        tier="Potente",
        description="Estado del arte, máxima calidad de imagen.",
    ),
    ModelEntry(
        provider="openai",
        capability="image",
        value="gpt-image-1",
        label="GPT Image 1",
        tier="Balanceado",
        is_recommended=True,
        description="Balance sólido entre calidad y costo.",
    ),
    ModelEntry(
        provider="openai",
        capability="image",
        value="gpt-image-1-mini",
        label="GPT Image 1 Mini",
        tier="Eficiente",
        description="Generación rápida y económica.",
    ),
    ModelEntry(
        provider="openai",
        capability="image",
        value="dall-e-3",
        label="DALL-E 3",
        tier="Balanceado",
        description="Compatibilidad legacy para workflows que aún usan DALL-E 3.",
    ),
    # ── Gemini Image (Nano Banana) ───────────────────────────
    ModelEntry(
        provider="gemini",
        capability="image",
        value="gemini-3-pro-image-preview",
        label="Nano Banana Pro",
        tier="Potente",
        is_preview=True,
        description="Producción profesional con reasoning avanzado. Hasta 4K.",
    ),
    ModelEntry(
        provider="gemini",
        capability="image",
        value="gemini-3.1-flash-image-preview",
        label="Nano Banana 2",
        tier="Balanceado",
        is_preview=True,
        is_recommended=True,
        description="Alto volumen, rápido, hasta 4K. Search grounding.",
    ),
    ModelEntry(
        provider="gemini",
        capability="image",
        value="gemini-2.5-flash-image",
        label="Nano Banana",
        tier="Eficiente",
        description="Velocidad y eficiencia para alto volumen (1K).",
    ),
    # ── Imagen 4 (Google) ────────────────────────────────────
    ModelEntry(
        provider="imagen",
        capability="image",
        value="imagen-4.0-ultra-generate-001",
        label="Imagen 4 Ultra",
        tier="Potente",
        api_family="imagen",
        description="Máxima calidad fotorrealista. 1 imagen a la vez.",
    ),
    ModelEntry(
        provider="imagen",
        capability="image",
        value="imagen-4.0-generate-001",
        label="Imagen 4",
        tier="Balanceado",
        is_recommended=True,
        api_family="imagen",
        description="Generación fotorrealista de alta calidad. Hasta 4 imágenes.",
    ),
    ModelEntry(
        provider="imagen",
        capability="image",
        value="imagen-4.0-fast-generate-001",
        label="Imagen 4 Fast",
        tier="Eficiente",
        api_family="imagen",
        description="Generación rápida, ideal para iteración. Hasta 4 imágenes.",
    ),
    # ── Video / Creatomate ───────────────────────────────────
    ModelEntry(
        provider="creatomate",
        capability="video",
        value="creatomate-template",
        label="Creatomate Template",
        tier="Potente",
        description="Renderiza reels desde un template configurado en Creatomate.",
    ),
    ModelEntry(
        provider="creatomate",
        capability="video",
        value="creatomate-renderscript",
        label="Creatomate RenderScript",
        tier="Balanceado",
        is_recommended=True,
        description="Genera reels automáticamente desde el guion sin depender de template fijo.",
    ),
    # ── Video / Google Veo ───────────────────────────────────
    ModelEntry(
        provider="veo",
        capability="video",
        value="veo-3.1-generate-preview",
        label="Veo 3.1",
        tier="Potente",
        is_preview=True,
        description="Video generativo premium para clips cortos con alto nivel visual.",
    ),
    ModelEntry(
        provider="veo",
        capability="video",
        value="veo-3.1-fast-generate-preview",
        label="Veo 3.1 Fast",
        tier="Balanceado",
        is_preview=True,
        is_recommended=True,
        description="Generación más rápida para iteración y testing creativo.",
    ),
    ModelEntry(
        provider="veo",
        capability="video",
        value="veo-3.1-lite-generate-preview",
        label="Veo 3.1 Lite",
        tier="Eficiente",
        is_preview=True,
        description="Variante más económica para alto volumen.",
    ),
]


# ── Helpers ──────────────────────────────────────────────────


def get_models_for(provider: str, capability: CapabilityType) -> list[ModelEntry]:
    """Retorna modelos del catálogo filtrados por provider y capability."""
    return [m for m in _CATALOG if m.provider == provider and m.capability == capability]


def get_providers_for(capability: CapabilityType) -> list[str]:
    """Retorna lista de providers únicos que soportan una capability."""
    seen: set[str] = set()
    result: list[str] = []
    for m in _CATALOG:
        if m.capability == capability and m.provider not in seen:
            seen.add(m.provider)
            result.append(m.provider)
    return result


def get_catalog_as_choices(provider: str, capability: CapabilityType) -> list[tuple[str, str]]:
    """Retorna lista de (value, label) para un <select> HTML, agrupado por tier."""
    models = get_models_for(provider, capability)
    tier_order: dict[TierType, int] = {"Potente": 0, "Balanceado": 1, "Eficiente": 2}
    models.sort(key=lambda m: tier_order.get(m.tier, 99))

    choices: list[tuple[str, str]] = []
    for m in models:
        suffix_parts: list[str] = []
        if m.is_preview:
            suffix_parts.append("Preview")
        if m.is_recommended:
            suffix_parts.append("★")
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        label = f"{m.label} — {m.tier}{suffix}"
        choices.append((m.value, label))
    return choices


def is_catalog_model(value: str, provider: str, capability: CapabilityType) -> bool:
    """Verifica si un model ID pertenece al catálogo para un provider/capability."""
    return any(
        m.value == value and m.provider == provider and m.capability == capability
        for m in _CATALOG
    )


def get_catalog_as_grouped_dict() -> dict[str, dict[str, list[dict]]]:
    """Retorna catálogo agrupado por provider→capability→[model dicts] para JS."""
    result: dict[str, dict[str, list[dict]]] = {}
    for m in _CATALOG:
        provider_dict = result.setdefault(m.provider, {})
        cap_list = provider_dict.setdefault(m.capability, [])
        cap_list.append({
            "value": m.value,
            "label": m.label,
            "tier": m.tier,
            "is_preview": m.is_preview,
            "is_recommended": m.is_recommended,
            "description": m.description,
        })
    return result


def get_catalog_json() -> str:
    """Retorna JSON serializado del catálogo agrupado, listo para inyectar en template."""
    return json.dumps(get_catalog_as_grouped_dict(), ensure_ascii=False)
