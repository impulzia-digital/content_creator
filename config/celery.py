import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("contenido_ig")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Colas especializadas por tipo de trabajo
app.conf.task_routes = {
    "apps.content.tasks.*": {"queue": "generation"},
    "apps.assets.tasks.*": {"queue": "generation"},
    "apps.publishing.tasks.*": {"queue": "publishing"},
    "apps.agents.tasks.*": {"queue": "generation"},
}

app.autodiscover_tasks()
