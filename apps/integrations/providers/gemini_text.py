"""Gemini text generation provider."""

from __future__ import annotations

import asyncio
import logging

from django.conf import settings
from google import genai
from google.genai import types

from apps.integrations.base import (
    TextGenerationRequest,
    TextGenerationResponse,
    TextProvider,
)

logger = logging.getLogger(__name__)

_LONG_CONTEXT_THRESHOLD = 200_000

_COST_PER_1M = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
}

_LONG_CONTEXT_COST_PER_1M = {
    "gemini-2.5-pro": {"input": 2.50, "output": 15.00},
    "gemini-3.1-pro-preview": {"input": 4.00, "output": 18.00},
}


class GeminiTextProvider(TextProvider):
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        config_kwargs = {
            "system_instruction": request.system_prompt,
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }
        if request.response_format == "json_object":
            config_kwargs["response_mime_type"] = "application/json"

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=request.model,
            contents=request.user_prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        thoughts_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)

        cost = 0.0
        rates = _resolve_rates(request.model, prompt_tokens)
        if rates:
            cost = (
                prompt_tokens * rates["input"] / 1_000_000
                + (completion_tokens + thoughts_tokens) * rates["output"] / 1_000_000
            )

        return TextGenerationResponse(
            text=_extract_text(response),
            model=getattr(response, "model_version", request.model) or request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens + thoughts_tokens,
            cost_usd=cost,
            raw_response=_dump_response(response),
        )


def _extract_text(response: types.GenerateContentResponse) -> str:
    if getattr(response, "text", None):
        return response.text

    parts: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            if getattr(part, "thought", None) is True:
                continue
            if getattr(part, "text", None):
                parts.append(part.text)
    return "".join(parts)


def _resolve_rates(model: str, prompt_tokens: int) -> dict[str, float]:
    if prompt_tokens > _LONG_CONTEXT_THRESHOLD and model in _LONG_CONTEXT_COST_PER_1M:
        return _LONG_CONTEXT_COST_PER_1M[model]
    return _COST_PER_1M.get(model, {})


def _dump_response(response: types.GenerateContentResponse) -> dict:
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", exclude_none=True)
    return {}