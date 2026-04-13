# 📸 Creador de Contenido — Instagram

Sistema automatizado de creación y publicación de contenido para Instagram,
impulsado por sub-agentes de IA (OpenAI) con orquestación Celery.

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5 · Python 3.12 |
| Tasks | Celery + Redis (3 queues) |
| DB | PostgreSQL 16 |
| IA Texto | OpenAI GPT-4o / GPT-4o-mini |
| IA Imágenes | OpenAI gpt-image-1 / DALL-E 3 |
| Storage | S3-compatible (Cloudflare R2) |
| Publishing | Meta Graph API v21.0 |
| Frontend | Django Templates + HTMX + Tailwind |
| Deploy | Docker → Railway (3 servicios) |

## Arquitectura de sub-agentes

```
ContentBrief (input)
   │
   ├→ BriefEnricherAgent   — enriquece la idea cruda
   ├→ ImageAgent / CarouselAgent / VideoAgent — genera assets
   ├→ CopyAgent             — escribe caption + alt_text
   └→ HashtagAgent          — genera hashtags categorizados
   │
ContentVariant (output) → ApprovalRequest → PublishingSchedule → Instagram
```

## Setup local

```bash
# 1. Copiar variables de entorno
cp .env.example .env

# 2. Configurar NGROK_AUTHTOKEN y, si aplica, NGROK_DOMAIN en .env

# 3. Levantar con Docker (web + worker + beat + ngrok)
docker compose up --build

# 4. Crear superusuario
docker compose exec web python manage.py createsuperuser

# 5. Acceder
# http://localhost:8000/admin/
# http://localhost:8000/
# http://localhost:4040/  (inspector local de ngrok)
```

## Tests

```bash
docker compose exec web pytest -x -v
```

## Deploy (Railway)

1. Crear proyecto en Railway
2. Agregar PostgreSQL y Redis como plugins
3. Configurar variables de entorno (ver `.env.example`)
4. Deploy desde GitHub → Railway usa el `Dockerfile` y `railway.toml`

Los 3 servicios (web, worker, beat) se despliegan desde el mismo Docker image.

## Estructura

```
config/               # Django settings, celery, urls, wsgi
apps/
  common/             # TimeStampedModel, AuditEvent, middleware
  brands/             # Brand, InstagramAccount, Membership
  content/            # ContentBrief, ContentVariant, AgentRun
  assets/             # Asset (image, video, thumbnail)
  approvals/          # ApprovalRequest
  publishing/         # PublishingSchedule, Publication
  integrations/       # ABCs + providers (OpenAI, Meta, S3)
  agents/             # Sub-agentes + orchestrator + prompts
templates/            # Django templates (HTMX + Tailwind)
tests/                # pytest test suite
```
