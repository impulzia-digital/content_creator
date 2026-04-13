"""
BaseAgent — Clase base abstracta para todos los sub-agentes.

Cada agente hereda de BaseAgent e implementa:
    - build_prompt(): construir system + user prompt
    - parse_output(): parsear la respuesta del proveedor
    - execute(): lógica principal (opcionalmente override)
"""

from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from apps.content.models import AgentRun, ContentBrief, ContentVariant
from apps.brands.models import Brand

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Contexto inyectado a cada agente."""
    brief: ContentBrief
    brand: Brand
    variant: ContentVariant | None = None
    extra: dict = field(default_factory=dict)

    @property
    def brand_briefing(self) -> str:
        return self.brand.get_brand_briefing()


@dataclass
class AgentResult:
    """Resultado devuelto por un agente."""
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    cost_usd: float = 0.0
    provider: str = ""
    model: str = ""
    duration_seconds: float = 0.0


class BaseAgent(abc.ABC):
    """Clase base para sub-agentes de generación de contenido."""

    agent_type: str = ""  # Debe coincidir con AgentRun.AgentType

    @abc.abstractmethod
    async def build_prompt(self, context: AgentContext) -> tuple[str, str]:
        """Retorna (system_prompt, user_prompt)."""
        ...

    @abc.abstractmethod
    async def parse_output(self, raw_output: Any, context: AgentContext) -> dict:
        """Parsea la respuesta del proveedor y retorna datos estructurados."""
        ...

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Flujo estándar:
        1. Crear AgentRun (status=running)
        2. build_prompt()
        3. Llamar al proveedor
        4. parse_output()
        5. Actualizar AgentRun (status=success/failed)
        6. Retornar AgentResult
        """
        start = time.monotonic()

        # Crear registro de ejecución
        run = await self._create_run(context)

        try:
            result = await self._do_execute(context)
            elapsed = time.monotonic() - start
            result.duration_seconds = elapsed

            # Actualizar run
            run.status = AgentRun.RunStatus.SUCCESS
            run.output_data = result.data
            run.cost_usd = result.cost_usd
            run.provider = result.provider
            run.model = result.model
            run.duration_seconds = elapsed
            await run.asave()

            logger.info(
                "Agent %s completado en %.1fs — cost=$%.4f",
                self.agent_type, elapsed, result.cost_usd,
            )
            return result

        except Exception as exc:
            elapsed = time.monotonic() - start
            run.status = AgentRun.RunStatus.FAILED
            run.error_detail = str(exc)
            run.duration_seconds = elapsed
            await run.asave()

            logger.exception("Agent %s falló: %s", self.agent_type, exc)
            return AgentResult(
                success=False,
                error=str(exc),
                duration_seconds=elapsed,
            )

    @abc.abstractmethod
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """Implementación específica de cada agente."""
        ...

    async def _create_run(self, context: AgentContext) -> AgentRun:
        run = AgentRun(
            brief=context.brief,
            variant=context.variant,
            agent_type=self.agent_type,
            status=AgentRun.RunStatus.RUNNING,
            input_data={
                "title": context.brief.title,
                "content_type": context.brief.content_type,
                "raw_idea": context.brief.raw_idea[:500],
            },
        )
        await run.asave()
        return run
