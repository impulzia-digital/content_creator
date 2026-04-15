"""
Celery tasks para generación de contenido.
"""

import logging

from asgiref.sync import async_to_sync
from celery import shared_task

from apps.content.models import ContentBrief

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="content.generate_content",
    queue="generation",
    max_retries=2,
    soft_time_limit=840,
    time_limit=900,
)
def generate_content_task(self, brief_id: str) -> dict:
    """
    Tarea principal: orquestar la generación de contenido para un brief.
    """
    from apps.agents.orchestrator import ContentOrchestrator

    try:
        brief = ContentBrief.objects.get(pk=brief_id)
    except ContentBrief.DoesNotExist:
        logger.error("Brief %s no encontrado", brief_id)
        return {"error": f"Brief {brief_id} no encontrado"}

    orchestrator = ContentOrchestrator()
    result = async_to_sync(orchestrator.generate_content)(brief)

    if not result.get("success") and self.request.retries < self.max_retries:
        raise self.retry(countdown=30 * (self.request.retries + 1))

    return result
