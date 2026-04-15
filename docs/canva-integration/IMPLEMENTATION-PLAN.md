# Plan de Implementación — Canva Integration

> **Estado**: No iniciado  
> **Dependencia bloqueante**: Cuenta Canva Enterprise + credenciales de Developer Portal  
> **Estimación**: 4 fases secuenciales

---

## Resumen

Integrar Canva Connect API como proveedor de imagen adicional (`"canva"`) con dos modos:

- **Ruta Canva**: LLM genera campos estructurados → Canva rellena plantilla → exporta JPG → S3
- **Ruta Híbrida**: IA genera imagen base (OpenAI/Gemini/Imagen) → se sube a Canva → Canva compone diseño final con branding → exporta JPG → S3

La integración reutiliza el patrón existente de providers (ABC → registry → routing → catalog) y convive con los providers actuales sin romper nada.

---

## Fase 1: Fundación — Conexión con Canva y cliente API

**Dependencias**: Ninguna (fase independiente)

### 1.1 — Modelo `CanvaAccount`

**Archivo**: `apps/brands/models.py` (añadir junto a `InstagramAccount`)

Crear modelo similar a `InstagramAccount` para OAuth de Canva:

```python
class CanvaAccount(models.Model):
    brand = models.OneToOneField("brands.Brand", on_delete=models.CASCADE, related_name="canva_account")
    canva_user_id = models.CharField(max_length=100, blank=True)
    access_token = models.TextField(help_text="Cifrar en producción")
    refresh_token = models.TextField(help_text="Cifrar en producción")
    token_expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cuenta Canva"
        verbose_name_plural = "Cuentas Canva"

    def __str__(self):
        return f"Canva – {self.brand.name}"

    @property
    def is_token_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.token_expires_at
```

**Referencia**: seguir patrón de `InstagramAccount` en línea ~95 de `apps/brands/models.py`.

### 1.2 — Modelo `CanvaTemplate`

**Archivo**: `apps/brands/models.py`

```python
class CanvaTemplate(models.Model):
    class ContentType(models.TextChoices):
        POST = "post", "Post"
        CAROUSEL = "carousel", "Carrusel"
        STORY = "story", "Story"
        REEL = "reel", "Reel"

    class AspectRatio(models.TextChoices):
        SQUARE = "1:1", "1:1 (Cuadrado)"
        PORTRAIT = "4:5", "4:5 (Retrato)"
        VERTICAL = "9:16", "9:16 (Vertical)"
        LANDSCAPE = "16:9", "16:9 (Horizontal)"

    brand = models.ForeignKey("brands.Brand", on_delete=models.CASCADE, related_name="canva_templates")
    canva_brand_template_id = models.CharField(max_length=200, help_text="ID de la Brand Template en Canva")
    name = models.CharField(max_length=200, help_text="Nombre descriptivo")
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    aspect_ratio = models.CharField(max_length=10, choices=AspectRatio.choices, default="4:5")
    autofill_fields = models.JSONField(
        default=dict, blank=True,
        help_text="Schema de campos autofillables (cacheado de Canva)",
    )
    is_default = models.BooleanField(default=False, help_text="Plantilla default para este content_type")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla Canva"
        verbose_name_plural = "Plantillas Canva"
        unique_together = [("brand", "canva_brand_template_id")]

    def __str__(self):
        return f"{self.name} ({self.content_type}) – {self.brand.name}"
```

### 1.3 — Settings de Canva

**Archivo**: `config/settings/base.py`

Añadir al final de la sección de providers:

```python
# ── Canva Connect API ────────────────────────────
CANVA_CLIENT_ID = env("CANVA_CLIENT_ID", default="")
CANVA_CLIENT_SECRET = env("CANVA_CLIENT_SECRET", default="")
CANVA_REDIRECT_URI = env("CANVA_REDIRECT_URI", default="http://localhost:8000/brands/canva/callback/")
CANVA_API_BASE_URL = env("CANVA_API_BASE_URL", default="https://api.canva.com/rest/v1")
```

**Variables `.env`**:
```env
CANVA_CLIENT_ID=
CANVA_CLIENT_SECRET=
CANVA_REDIRECT_URI=https://tu-dominio.com/brands/canva/callback/
CANVA_API_BASE_URL=https://api.canva.com/rest/v1
```

### 1.4 — Cliente base de Canva API

**Archivo nuevo**: `apps/integrations/providers/canva_client.py`

Wrapper HTTP async para todas las operaciones de Canva:

```python
"""Cliente base para Canva Connect API v1."""

import asyncio
import httpx
from django.conf import settings
from apps.brands.models import CanvaAccount


class CanvaAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Canva API {status_code}: {message}")


class CanvaClient:
    """Async client for Canva Connect API."""

    BASE_URL = "https://api.canva.com/rest/v1"
    POLL_INTERVAL = 2        # seconds (initial)
    POLL_MAX_INTERVAL = 10   # seconds (max backoff)
    POLL_TIMEOUT = 120       # seconds (total)

    def __init__(self, canva_account: CanvaAccount):
        self.account = canva_account
        self._client: httpx.AsyncClient | None = None

    async def _ensure_token(self):
        """Refresh access token if expired."""
        if self.account.is_token_expired:
            await self._refresh_token()

    async def _refresh_token(self):
        """Exchange refresh token for new access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.canva.com/rest/v1/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.account.refresh_token,
                    "client_id": settings.CANVA_CLIENT_ID,
                    "client_secret": settings.CANVA_CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            from django.utils import timezone
            from datetime import timedelta
            self.account.access_token = data["access_token"]
            self.account.refresh_token = data.get("refresh_token", self.account.refresh_token)
            self.account.token_expires_at = timezone.now() + timedelta(seconds=data["expires_in"])
            await asyncio.to_thread(self.account.save)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.account.access_token}",
            "Content-Type": "application/json",
        }

    # ── Brand Templates ──

    async def get_brand_template_dataset(self, template_id: str) -> dict:
        """GET /brand-templates/{id}/dataset — obtener campos autofillables."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/brand-templates/{template_id}/dataset",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    # ── Autofill ──

    async def create_autofill_job(self, template_id: str, data: dict) -> dict:
        """POST /autofills — crear job de autofill."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/autofills",
                headers=self._headers(),
                json={
                    "brand_template_id": template_id,
                    "data": data,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_autofill_job(self, job_id: str) -> dict:
        """GET /autofills/{id} — polling de estado."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/autofills/{job_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def wait_for_autofill(self, job_id: str) -> dict:
        """Poll autofill job until complete with exponential backoff."""
        return await self._poll_job(
            lambda: self.get_autofill_job(job_id)
        )

    # ── Exports ──

    async def create_export_job(self, design_id: str, fmt: str = "jpg") -> dict:
        """POST /exports — exportar diseño como imagen."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/exports",
                headers=self._headers(),
                json={
                    "design_id": design_id,
                    "format": {"type": fmt},
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_export_job(self, job_id: str) -> dict:
        """GET /exports/{id} — polling de exportación."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/exports/{job_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def wait_for_export(self, job_id: str) -> dict:
        """Poll export job until complete."""
        return await self._poll_job(
            lambda: self.get_export_job(job_id)
        )

    # ── Asset Uploads ──

    async def upload_asset(self, image_bytes: bytes, name: str = "asset") -> dict:
        """POST /asset-uploads — subir imagen a Canva."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/asset-uploads",
                headers={
                    "Authorization": f"Bearer {self.account.access_token}",
                },
                files={"file": (f"{name}.jpg", image_bytes, "image/jpeg")},
                data={"name": name},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_asset_upload_job(self, job_id: str) -> dict:
        """GET /asset-uploads/{id} — polling de upload."""
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/asset-uploads/{job_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def wait_for_upload(self, job_id: str) -> dict:
        """Poll upload job until complete."""
        return await self._poll_job(
            lambda: self.get_asset_upload_job(job_id)
        )

    # ── Polling helper ──

    async def _poll_job(self, get_fn, timeout: float | None = None) -> dict:
        """Generic polling with exponential backoff."""
        timeout = timeout or self.POLL_TIMEOUT
        interval = self.POLL_INTERVAL
        elapsed = 0.0

        while elapsed < timeout:
            result = await get_fn()
            job = result.get("job", result)
            status = job.get("status", "")

            if status == "success":
                return result
            if status == "failed":
                raise CanvaAPIError(0, f"Job failed: {job}")

            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval * 1.5, self.POLL_MAX_INTERVAL)

        raise CanvaAPIError(0, f"Job timeout after {timeout}s")
```

### 1.5 — Flujo OAuth

**Archivos**: `apps/brands/views.py` + `apps/brands/urls.py`

Crear 3 vistas:

```python
# En apps/brands/views.py (añadir)

import hashlib
import secrets
import base64
from urllib.parse import urlencode
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import httpx


@login_required
def canva_connect(request, brand_id):
    """Inicia flujo OAuth con Canva."""
    brand = get_object_or_404(Brand, pk=brand_id)
    # Generar PKCE
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    # Guardar en session
    request.session["canva_code_verifier"] = code_verifier
    request.session["canva_brand_id"] = brand_id

    params = urlencode({
        "response_type": "code",
        "client_id": settings.CANVA_CLIENT_ID,
        "redirect_uri": settings.CANVA_REDIRECT_URI,
        "scope": "design:content:read design:content:write design:meta:read "
                 "brandtemplate:meta:read brandtemplate:content:read "
                 "asset:read asset:write",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": str(brand_id),
    })
    return redirect(f"https://www.canva.com/api/oauth/authorize?{params}")


@login_required
def canva_callback(request):
    """Callback de OAuth — intercambia code por tokens."""
    code = request.GET.get("code")
    state = request.GET.get("state")
    code_verifier = request.session.pop("canva_code_verifier", None)
    brand_id = request.session.pop("canva_brand_id", None)

    if not code or not code_verifier:
        messages.error(request, "Error en la autorización de Canva.")
        return redirect("brands:brand_list")

    # Intercambiar code por tokens
    resp = httpx.post(
        "https://api.canva.com/rest/v1/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.CANVA_REDIRECT_URI,
            "client_id": settings.CANVA_CLIENT_ID,
            "client_secret": settings.CANVA_CLIENT_SECRET,
            "code_verifier": code_verifier,
        },
    )
    if resp.status_code != 200:
        messages.error(request, f"Error al conectar Canva: {resp.text}")
        return redirect("brands:brand_list")

    data = resp.json()
    from django.utils import timezone
    from datetime import timedelta
    from apps.brands.models import CanvaAccount

    CanvaAccount.objects.update_or_create(
        brand_id=brand_id,
        defaults={
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_expires_at": timezone.now() + timedelta(seconds=data["expires_in"]),
            "canva_user_id": data.get("user_id", ""),
            "is_active": True,
        },
    )
    messages.success(request, "Canva conectado exitosamente.")
    return redirect("brands:brand_detail", pk=brand_id)


@login_required
def canva_disconnect(request, brand_id):
    """Desconecta Canva de una marca."""
    from apps.brands.models import CanvaAccount
    CanvaAccount.objects.filter(brand_id=brand_id).update(is_active=False)
    messages.success(request, "Canva desconectado.")
    return redirect("brands:brand_detail", pk=brand_id)
```

**URLs** (añadir en `apps/brands/urls.py`):

```python
path("canva/connect/<int:brand_id>/", views.canva_connect, name="canva_connect"),
path("canva/callback/", views.canva_callback, name="canva_callback"),
path("canva/disconnect/<int:brand_id>/", views.canva_disconnect, name="canva_disconnect"),
```

### 1.6 — Admin de Canva

**Archivo**: `apps/brands/admin.py`

```python
class CanvaAccountInline(admin.StackedInline):
    model = CanvaAccount
    extra = 0
    max_num = 1
    readonly_fields = ("canva_user_id", "token_expires_at", "created_at", "updated_at")

class CanvaTemplateInline(admin.TabularInline):
    model = CanvaTemplate
    extra = 0
    fields = ("name", "canva_brand_template_id", "content_type", "aspect_ratio", "is_default", "is_active")

# Añadir ambos inlines al BrandAdmin existente:
# inlines = [..., CanvaAccountInline, CanvaTemplateInline]
```

### 1.7 — Migración

```bash
python manage.py makemigrations brands --name canva_integration
python manage.py migrate
```

---

## Fase 2: Ruta Canva — Provider de imagen basado en plantillas

**Dependencias**: Fase 1 completa

### 2.1 — `CanvaImageProvider`

**Archivo nuevo**: `apps/integrations/providers/canva_images.py`

```python
"""Canva image provider — genera imágenes via Brand Template Autofill."""

from apps.integrations.base import ImageGenerationRequest, ImageGenerationResponse, ImageProvider
from apps.integrations.providers.canva_client import CanvaClient, CanvaAPIError
from apps.brands.models import CanvaAccount
import httpx
import json


class CanvaImageProvider(ImageProvider):
    """ImageProvider que rellena plantillas de Canva en vez de generar imágenes."""

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        # 1. Obtener CanvaAccount para la marca
        account = await self._get_account(request.brand_id)
        client = CanvaClient(account)

        # 2. Parsear los campos de autofill del prompt (JSON)
        autofill_data = json.loads(request.prompt) if isinstance(request.prompt, str) else request.prompt

        # 3. template_id viene en request.model
        template_id = request.model

        # 4. Crear job de autofill
        autofill_result = await client.create_autofill_job(template_id, autofill_data)
        job_id = autofill_result["job"]["id"]

        # 5. Esperar autofill
        result = await client.wait_for_autofill(job_id)
        design_id = result["job"]["result"]["design"]["id"]

        # 6. Exportar como JPG
        export_result = await client.create_export_job(design_id, fmt="jpg")
        export_job_id = export_result["job"]["id"]

        # 7. Esperar export
        export_done = await client.wait_for_export(export_job_id)
        urls = export_done["job"]["result"]["urls"]

        # 8. Descargar imágenes
        image_bytes_list = []
        async with httpx.AsyncClient() as http:
            for url in urls:
                resp = await http.get(url)
                resp.raise_for_status()
                image_bytes_list.append(resp.content)

        return ImageGenerationResponse(
            image_urls=urls,
            image_bytes=image_bytes_list,
            model=f"canva:{template_id}",
            cost_usd=0.0,  # Incluido en suscripción Enterprise
            width=request.width,
            height=request.height,
            content_type="image/jpeg",
        )

    @staticmethod
    async def _get_account(brand_id: int | None) -> CanvaAccount:
        if not brand_id:
            raise CanvaAPIError(0, "brand_id requerido para CanvaImageProvider")
        import asyncio
        account = await asyncio.to_thread(
            CanvaAccount.objects.get, brand_id=brand_id, is_active=True
        )
        return account
```

### 2.2 — Registrar en Registry

**Archivo**: `apps/integrations/registry.py`

Añadir en `get_image_provider()`:

```python
elif provider == "canva":
    from apps.integrations.providers.canva_images import CanvaImageProvider
    return CanvaImageProvider()
```

**Nota**: `CanvaImageProvider` NO usa `@lru_cache` porque no necesita configuración global. El contexto de marca se resuelve dentro de `generate()`.

### 2.3 — Registrar en Routing

**Archivo**: `apps/integrations/routing.py`

```python
# Añadir "canva" al set:
_SUPPORTED_PROVIDERS = {
    "text": {"openai", "gemini"},
    "image": {"openai", "gemini", "imagen", "canva"},  # ← añadir
    "video": {"creatomate", "veo"},
}

# Añadir branch en _default_model_for():
elif provider == "canva":
    return "canva-autofill"  # El template real se resuelve en runtime por marca
```

### 2.4 — Registrar en Model Catalog

**Archivo**: `apps/integrations/model_catalog.py`

```python
ModelEntry(
    provider="canva",
    capability="image",
    value="canva-autofill",
    label="Canva (Autofill de plantilla)",
    tier="Balanceado",
    description="Rellena plantillas de marca en Canva automáticamente.",
),
```

### 2.5 — Adaptar `ImageAgent` para Ruta Canva

**Archivo**: `apps/agents/image_agent.py`

En `_do_execute()`, añadir branch:

```python
# Cuando provider es "canva":
if resolved.provider == "canva":
    # 1. Obtener schema de campos de la plantilla
    template = CanvaTemplate.objects.filter(
        brand=brief.brand, content_type=brief.content_type, is_default=True, is_active=True
    ).first()

    # 2. LLM genera campos de autofill (no un prompt visual)
    autofill_prompt = f"""
    Genera los valores para rellenar esta plantilla de Canva.
    Campos disponibles: {json.dumps(template.autofill_fields)}
    Tema del contenido: {brief.enriched_brief or brief.raw_idea}
    Marca: {brief.brand.name}
    Responde SOLO con JSON válido con los campos y sus valores.
    """
    text_response = await text_provider.generate(TextGenerationRequest(
        system_prompt="Eres un copywriter de marca.",
        user_prompt=autofill_prompt,
        response_format="json_object",
    ))

    # 3. Pasar JSON como prompt al CanvaImageProvider
    image_request = ImageGenerationRequest(
        prompt=text_response.text,  # JSON con campos de autofill
        model=template.canva_brand_template_id,
        brand_id=brief.brand.id,  # Nuevo campo
    )
    response = await image_provider.generate(image_request)
```

### 2.6 — Adaptar `CarouselAgent` para Ruta Canva

**Archivo**: `apps/agents/carousel_agent.py`

Cuando provider es canva, usar template multipágina:

```python
if resolved.provider == "canva":
    # 1. Buscar template de carrusel
    template = CanvaTemplate.objects.filter(
        brand=brief.brand, content_type="carousel", is_default=True, is_active=True
    ).first()

    # 2. LLM genera estructura de N slides con campos por página
    # 3. UN SOLO autofill con datos de todas las páginas
    # 4. Export devuelve N URLs (una por página)
    # 5. Guardar cada URL como Asset con position
```

### 2.7 — Extender `ImageGenerationRequest`

**Archivo**: `apps/integrations/base.py`

```python
@dataclass
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 1080
    height: int = 1350
    model: str = ""
    style: str = ""
    num_images: int = 1
    output_format: str = "jpeg"
    brand_id: int | None = None  # ← NUEVO: para providers que necesitan contexto de marca (Canva)
```

---

## Fase 3: Ruta Híbrida — IA genera imagen base + Canva compone

**Dependencias**: Fase 1 + Fase 2 completas

### 3.1 — Servicio `CanvaCompositor`

**Archivo nuevo**: `apps/integrations/providers/canva_compositor.py`

```python
"""Compositor que toma una imagen generada por IA y la compone con branding via Canva."""

from dataclasses import dataclass
from apps.integrations.providers.canva_client import CanvaClient
from apps.brands.models import CanvaAccount, CanvaTemplate
import httpx


@dataclass
class CompositionRequest:
    base_image_bytes: bytes | None = None
    base_image_url: str = ""
    brand_id: int = 0
    template_id: str = ""
    text_fields: dict = None  # headline, body, cta, etc.
    content_type: str = "post"


@dataclass
class CompositionResponse:
    image_urls: list[str] = None
    image_bytes: list[bytes] = None
    design_id: str = ""
    cost_usd: float = 0.0


class CanvaCompositor:
    """Compone imagen IA + branding usando plantillas de Canva."""

    async def compose(self, request: CompositionRequest) -> CompositionResponse:
        # 1. Obtener cuenta y cliente
        import asyncio
        account = await asyncio.to_thread(
            CanvaAccount.objects.get, brand_id=request.brand_id, is_active=True
        )
        client = CanvaClient(account)

        # 2. Obtener bytes de la imagen base
        if request.base_image_bytes:
            img_bytes = request.base_image_bytes
        elif request.base_image_url:
            async with httpx.AsyncClient() as http:
                resp = await http.get(request.base_image_url)
                resp.raise_for_status()
                img_bytes = resp.content
        else:
            raise ValueError("Se necesita base_image_bytes o base_image_url")

        # 3. Subir imagen a Canva como asset
        upload_result = await client.upload_asset(img_bytes, name="ai-base-image")
        upload_job_id = upload_result["job"]["id"]
        upload_done = await client.wait_for_upload(upload_job_id)
        asset_id = upload_done["job"]["result"]["asset"]["id"]

        # 4. Preparar datos de autofill (imagen + textos)
        autofill_data = {
            **(request.text_fields or {}),
            "background_image": {"type": "image", "asset_id": asset_id},
        }

        # 5. Autofill
        autofill_result = await client.create_autofill_job(request.template_id, autofill_data)
        autofill_job_id = autofill_result["job"]["id"]
        autofill_done = await client.wait_for_autofill(autofill_job_id)
        design_id = autofill_done["job"]["result"]["design"]["id"]

        # 6. Export
        export_result = await client.create_export_job(design_id, fmt="jpg")
        export_job_id = export_result["job"]["id"]
        export_done = await client.wait_for_export(export_job_id)
        urls = export_done["job"]["result"]["urls"]

        # 7. Descargar
        image_bytes_list = []
        async with httpx.AsyncClient() as http:
            for url in urls:
                resp = await http.get(url)
                resp.raise_for_status()
                image_bytes_list.append(resp.content)

        return CompositionResponse(
            image_urls=urls,
            image_bytes=image_bytes_list,
            design_id=design_id,
        )
```

### 3.2 — Campo `canva_composition_enabled` en Brand

**Archivo**: `apps/brands/models.py`

```python
# Añadir a Brand:
canva_composition_enabled = models.BooleanField(
    default=False,
    help_text="Activar composición híbrida: IA genera imagen base + Canva aplica branding",
)
```

### 3.3 — Integrar en `ImageAgent`

**Archivo**: `apps/agents/image_agent.py`

En `_do_execute()`, después de generar la imagen con el provider normal:

```python
# Después de generar imagen con OpenAI/Gemini/Imagen:
if brief.brand.canva_composition_enabled:
    template = CanvaTemplate.objects.filter(
        brand=brief.brand, content_type=brief.content_type, is_default=True, is_active=True
    ).first()
    if template:
        compositor = CanvaCompositor()
        # LLM genera textos para overlays
        overlay_text = await text_provider.generate(...)
        composition = await compositor.compose(CompositionRequest(
            base_image_bytes=response.image_bytes[0],
            brand_id=brief.brand.id,
            template_id=template.canva_brand_template_id,
            text_fields=json.loads(overlay_text.text),
        ))
        # Reemplazar asset con imagen compuesta
        response = ImageGenerationResponse(
            image_bytes=composition.image_bytes,
            image_urls=composition.image_urls,
            ...
        )
```

### 3.4 — Migración

```bash
python manage.py makemigrations brands --name canva_composition_flag
python manage.py migrate
```

---

## Fase 4: Tests y verificación

**Dependencias**: Fases correspondientes completas

### 4.1 — Tests del cliente Canva

**Archivo nuevo**: `tests/test_canva_client.py`

| Test | Qué verifica |
|------|-------------|
| `test_refresh_token` | Token refresh automático cuando expira |
| `test_autofill_job_success` | Flujo completo autofill con mock |
| `test_export_job_success` | Flujo completo export con mock |
| `test_upload_asset_success` | Upload de asset con mock |
| `test_poll_timeout` | Timeout en polling lanza excepción |
| `test_poll_failure` | Job con status "failed" lanza excepción |

### 4.2 — Tests del CanvaImageProvider

**Archivo nuevo**: `tests/test_canva_images.py`

| Test | Qué verifica |
|------|-------------|
| `test_generate_single_image` | Autofill → export → download completo |
| `test_generate_multipage` | Template multipágina devuelve N imágenes |
| `test_missing_brand_id` | Error si no se pasa brand_id |
| `test_missing_account` | Error si no hay CanvaAccount activa |
| `test_cost_is_zero` | cost_usd siempre es 0.0 |

### 4.3 — Tests del CanvaCompositor

**Archivo nuevo**: `tests/test_canva_compositor.py`

| Test | Qué verifica |
|------|-------------|
| `test_compose_from_bytes` | Upload + autofill + export con imagen en bytes |
| `test_compose_from_url` | Descarga + upload + autofill + export |
| `test_missing_image` | Error sin imagen base |

### 4.4 — Tests de integración del pipeline

**Añadir a**: `tests/test_agents.py` o crear `tests/test_canva_pipeline.py`

| Test | Qué verifica |
|------|-------------|
| `test_image_agent_canva_route` | ImageAgent con provider="canva" genera autofill |
| `test_image_agent_hybrid_route` | ImageAgent con composición genera imagen + composición |
| `test_carousel_agent_canva` | CarouselAgent con canva usa batch autofill |
| `test_existing_providers_unaffected` | Providers existentes ignoran brand_id |

### 4.5 — Tests de routing y registry

**Añadir a**: `tests/test_integrations.py`

| Test | Qué verifica |
|------|-------------|
| `test_canva_in_supported_providers` | "canva" está en _SUPPORTED_PROVIDERS["image"] |
| `test_get_image_provider_canva` | get_image_provider("canva") retorna CanvaImageProvider |
| `test_catalog_includes_canva` | get_providers_for("image") incluye "canva" |

---

## Archivos — Resumen

### Archivos nuevos a crear

| Archivo | Fase | Propósito |
|---------|------|-----------|
| `apps/integrations/providers/canva_client.py` | 1 | Cliente HTTP para Canva Connect API |
| `apps/integrations/providers/canva_images.py` | 2 | CanvaImageProvider (Ruta Canva) |
| `apps/integrations/providers/canva_compositor.py` | 3 | CanvaCompositor (Ruta Híbrida) |
| `tests/test_canva_client.py` | 4 | Tests del cliente |
| `tests/test_canva_images.py` | 4 | Tests del provider |
| `tests/test_canva_compositor.py` | 4 | Tests del compositor |

### Archivos existentes a modificar

| Archivo | Fase | Cambio |
|---------|------|--------|
| `config/settings/base.py` | 1 | `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, `CANVA_REDIRECT_URI`, `CANVA_API_BASE_URL` |
| `apps/brands/models.py` | 1+3 | `CanvaAccount`, `CanvaTemplate`, `canva_composition_enabled` |
| `apps/brands/admin.py` | 1 | Inlines para `CanvaAccount` y `CanvaTemplate` |
| `apps/brands/urls.py` | 1 | Rutas OAuth (connect/callback/disconnect) |
| `apps/brands/views.py` | 1 | Vistas OAuth |
| `apps/integrations/base.py` | 2 | `brand_id` opcional en `ImageGenerationRequest` |
| `apps/integrations/registry.py` | 2 | Branch `"canva"` en `get_image_provider()` |
| `apps/integrations/routing.py` | 2 | `"canva"` en `_SUPPORTED_PROVIDERS["image"]` |
| `apps/integrations/model_catalog.py` | 2 | `ModelEntry` para canva |
| `apps/agents/image_agent.py` | 2+3 | Branch Ruta Canva + paso de composición |
| `apps/agents/carousel_agent.py` | 2+3 | Branch Ruta Canva (batch) + composición |
| `tests/test_integrations.py` | 4 | Tests de registry y routing con canva |
| `tests/test_agents.py` | 4 | Tests de pipeline con canva |

---

## Decisiones de diseño

1. **Canva como ImageProvider (misma ABC)**: Maximiza reutilización del patrón existente.
2. **`model` = `template_id`**: El template real se busca por marca + content_type en runtime.
3. **OAuth por marca**: Cada marca tiene su propio `CanvaAccount` (como `InstagramAccount`).
4. **Ruta Híbrida con flag explícito**: `canva_composition_enabled` en Brand, no automático.
5. **Solo ImageProvider**: No se añade Canva como provider de texto ni de video.
6. **Templates preconfigurados**: Se registran manualmente en admin, no auto-discovery.
7. **`autofill_fields` cacheado**: El schema se guarda en `CanvaTemplate` para evitar API calls extras.
8. **`brand_id` opcional en request**: Field nuevo que providers existentes ignoran.

---

## Verificación final

```bash
# 1. Tests unitarios
pytest tests/test_canva_client.py
pytest tests/test_canva_images.py
pytest tests/test_canva_compositor.py

# 2. Tests de integración
pytest tests/test_integrations.py
pytest tests/test_agents.py

# 3. Suite completa (nada roto)
pytest

# 4. Manual: crear brief con provider="canva"
# 5. Manual: crear brief con provider="openai" + composición habilitada
# 6. Manual: verificar "Canva" en dropdowns de admin
```
