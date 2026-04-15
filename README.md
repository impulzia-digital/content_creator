# 📸 Creador de Contenido — Instagram

Sistema automatizado de creación y publicación de contenido para Instagram,
impulsado por sub-agentes de IA (OpenAI o Gemini) con orquestación Celery.

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5 · Python 3.12 |
| Tasks | Celery + Redis (3 queues) |
| DB | PostgreSQL 16 |
| IA Texto | OpenAI GPT-4o / GPT-4o-mini o Gemini 2.5 |
| IA Imágenes | OpenAI gpt-image-1 / DALL-E 3 o Gemini Image |
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

# 4. Definir la clave del usuario seed en .env
# SEED_OWNER_PASSWORD=change-me

# 5. Cargar la seed versionada del negocio
docker compose exec web python manage.py seed_business_data

# 6. Si no querés usar el usuario seed, crear superusuario manual
docker compose exec web python manage.py createsuperuser

# 7. Acceder
# http://localhost:8000/admin/
# http://localhost:8000/
# http://localhost:4040/  (inspector local de ngrok)
```

## Tests

```bash
docker compose exec web pytest -x -v
```

## Seed versionada

El repo ahora puede cargar configuración base del negocio y briefs iniciales desde `seed_data/`.

- `brand.json`: identidad, tono, paleta y defaults editoriales.
- `users.json`: usuarios mínimos para entrar al backoffice.
- `memberships.json`: vínculo usuario ↔ marca.
- `instagram_accounts.json`: opcional; puede ir vacío si todavía no conectaste Meta.
- `briefs.json`: backlog inicial de `ContentBrief` versionado en Git.

Comandos:

```bash
docker compose exec web python manage.py seed_business_data
docker compose exec web python manage.py seed_business_data --dry-run
```

No guardes tokens ni passwords reales en `seed_data/`. Para valores sensibles usá `password_env` o `access_token_env` y definí esas variables en `.env`.

## Deploy (Railway)

1. Crear proyecto en Railway
2. Agregar PostgreSQL y Redis como plugins
3. Configurar variables de entorno (ver `.env.example`)
4. Deploy desde GitHub → Railway usa el `Dockerfile` y `railway.toml`

Los 3 servicios (web, worker, beat) se despliegan desde el mismo Docker image.

## Providers IA

- `TEXT_PROVIDER`: `openai` o `gemini`
- `IMAGE_PROVIDER`: `openai`, `gemini` o `imagen`
- Las marcas pueden definir defaults por agente en `ai_provider_defaults`
- Los briefs pueden sobrescribir texto e imagen en `ai_provider_overrides`
- Variables sugeridas para modelos base: `OPENAI_TEXT_MODEL`, `OPENAI_REASONING_MODEL`, `OPENAI_IMAGE_MODEL`, `GEMINI_TEXT_MODEL`, `GEMINI_REASONING_MODEL`, `GEMINI_IMAGE_MODEL`, `IMAGEN_MODEL`

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
