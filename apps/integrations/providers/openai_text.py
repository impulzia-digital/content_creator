"""OpenAI text generation provider."""

from __future__ import annotations

import logging

from django.conf import settings
from openai import AsyncOpenAI

from apps.integrations.base import (
    TextGenerationRequest,
    TextGenerationResponse,
    TextProvider,
)

logger = logging.getLogger(__name__)

# Costo aproximado por 1M tokens (USD) — se actualiza periódicamente
_COST_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
}


class OpenAITextProvider(TextProvider):
    def __init__(self, api_key: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        kwargs: dict = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        usage = response.usage

        cost = 0.0
        if usage and request.model in _COST_PER_1M:
            rates = _COST_PER_1M[request.model]
            cost = (
                usage.prompt_tokens * rates["input"] / 1_000_000
                + usage.completion_tokens * rates["output"] / 1_000_000
            )

        return TextGenerationResponse(
            text=choice.message.content or "",
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            cost_usd=cost,
            raw_response=response.model_dump(),
        )
