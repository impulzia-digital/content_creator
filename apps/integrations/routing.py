"""Resolution helpers for provider/model selection per capability and agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings


_COMPLEX_TEXT_AGENT_TYPES = {"carousel", "video"}
_SUPPORTED_PROVIDERS = {
    "text": {"openai", "gemini"},
    "image": {"openai", "gemini", "imagen"},
}


@dataclass(frozen=True)
class ResolvedGenerationConfig:
    capability: str
    provider: str
    model: str
    provider_source: str
    model_source: str

    def as_dict(self) -> dict[str, str]:
        return {
            "capability": self.capability,
            "provider": self.provider,
            "model": self.model,
            "provider_source": self.provider_source,
            "model_source": self.model_source,
        }


def resolve_generation_config(
    *,
    capability: str,
    agent_type: str,
    brand_defaults: dict[str, Any] | None = None,
    brief_overrides: dict[str, Any] | None = None,
) -> ResolvedGenerationConfig:
    if capability not in _SUPPORTED_PROVIDERS:
        raise ValueError(f"Capability desconocida: {capability}")

    provider, provider_source = _resolve_field(
        configs=(
            (brief_overrides or {}, "brief"),
            (brand_defaults or {}, "brand"),
        ),
        capability=capability,
        agent_type=agent_type,
        field="provider",
    )
    if not provider:
        provider = _default_provider_for(capability)
        provider_source = f"settings.{capability}_provider"

    provider = provider.strip().lower()
    if provider not in _SUPPORTED_PROVIDERS[capability]:
        raise ValueError(
            f"Provider '{provider}' no soportado para capability '{capability}'"
        )

    model, model_source = _resolve_field(
        configs=(
            (brief_overrides or {}, "brief"),
            (brand_defaults or {}, "brand"),
        ),
        capability=capability,
        agent_type=agent_type,
        field="model",
    )
    if not model:
        model = _default_model_for(provider=provider, capability=capability, agent_type=agent_type)
        model_source = f"settings.default_model.{provider}"

    return ResolvedGenerationConfig(
        capability=capability,
        provider=provider,
        model=model,
        provider_source=provider_source,
        model_source=model_source,
    )


def _resolve_field(
    *,
    configs: tuple[tuple[dict[str, Any], str], ...],
    capability: str,
    agent_type: str,
    field: str,
) -> tuple[str | None, str | None]:
    for config, label in configs:
        capability_config = config.get(capability)
        if not isinstance(capability_config, dict):
            continue

        for key in (agent_type, "default"):
            entry = capability_config.get(key)
            if isinstance(entry, dict):
                value = entry.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip(), f"{label}.{capability}.{key}.{field}"

        direct_value = capability_config.get(field)
        if isinstance(direct_value, str) and direct_value.strip():
            return direct_value.strip(), f"{label}.{capability}.{field}"

    return None, None


def _default_provider_for(capability: str) -> str:
    if capability == "image":
        return getattr(settings, "IMAGE_PROVIDER", "openai")
    return getattr(settings, "TEXT_PROVIDER", "openai")


def _default_model_for(*, provider: str, capability: str, agent_type: str) -> str:
    if capability == "image":
        if provider == "gemini":
            return getattr(settings, "GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
        if provider == "imagen":
            return getattr(settings, "IMAGEN_MODEL", "imagen-4.0-generate-001")
        return getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")

    is_complex_agent = agent_type in _COMPLEX_TEXT_AGENT_TYPES
    if provider == "gemini":
        if is_complex_agent:
            return getattr(settings, "GEMINI_REASONING_MODEL", "gemini-2.5-pro")
        return getattr(settings, "GEMINI_TEXT_MODEL", "gemini-2.5-flash")

    if is_complex_agent:
        return getattr(settings, "OPENAI_REASONING_MODEL", "gpt-5.4")
    return getattr(settings, "OPENAI_TEXT_MODEL", "gpt-5.4-mini")