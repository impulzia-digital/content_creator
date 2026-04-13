from importlib.util import find_spec

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# ── Ngrok (túnel público para desarrollo) ─────────────────────
NGROK_DOMAIN = config("NGROK_DOMAIN", default="")  # noqa: F405
NGROK_URL = config(  # noqa: F405
    "NGROK_URL",
    default=(f"https://{NGROK_DOMAIN}" if NGROK_DOMAIN else "https://underzealously-semiherbaceous-rena.ngrok-free.dev"),
)
CSRF_TRUSTED_ORIGINS = [NGROK_URL]
# URL pública para media (Instagram requiere URLs públicas para imágenes)
PUBLIC_MEDIA_BASE_URL = config("PUBLIC_MEDIA_BASE_URL", default=NGROK_URL)  # noqa: F405

# Celery en modo eager para desarrollo rápido (desactivar para probar colas)
# CELERY_TASK_ALWAYS_EAGER = True

# Debug-only tooling (optional in Docker/local mixed environments)
if find_spec("debug_toolbar"):
    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

if find_spec("django_extensions"):
    INSTALLED_APPS += ["django_extensions"]  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]
