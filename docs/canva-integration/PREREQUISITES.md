# Prerequisitos — Canva Integration

> Checklist de todo lo que hay que tener configurado **antes** de escribir código.

---

## 1. Cuenta Canva Enterprise

| Ítem | Detalle |
|------|---------|
| **Qué** | Suscripción Canva Enterprise |
| **Por qué** | La API de Autofill (Brand Template Autofill) **solo funciona con Enterprise**. Con cualquier otro plan, los endpoints retornan 403. |
| **Precio** | Negociable con ventas. No hay precio público. Contactar: [canva.com/enterprise](https://www.canva.com/enterprise/) |
| **Alternativa** | No hay. Sin Enterprise, la integración core no funciona. |
| **Verificación** | Loguearse en Canva → Settings → ver que el plan diga "Enterprise" |

---

## 2. Integración en Canva Developer Portal

| Paso | Acción |
|------|--------|
| 1 | Ir a [canva.com/developers](https://www.canva.com/developers/) |
| 2 | Click en "Create an integration" |
| 3 | Tipo: **Private** (no necesita revisión de Canva) |
| 4 | Nombre: "Creador de Contenido Instagram" (o similar) |
| 5 | Copiar el **Client ID** y **Client Secret** generados |

### Scopes a habilitar

Marcar estos scopes en la configuración de la integración:

| Scope | Propósito |
|-------|-----------|
| `design:content:read` | Leer contenido de diseños generados por autofill |
| `design:content:write` | Crear diseños nuevos via autofill |
| `design:meta:read` | Leer metadata (nombre, fechas) de diseños |
| `brandtemplate:meta:read` | Listar las Brand Templates disponibles |
| `brandtemplate:content:read` | Leer campos/dataset de las plantillas |
| `asset:read` | Leer assets subidos (imágenes) |
| `asset:write` | Subir imágenes a Canva (para Ruta Híbrida) |

> **Nota**: Todos los scopes marcados con `read` son obligatorios. Los `write` también, porque necesitamos crear diseños y subir assets.

### Redirect URI

Configurar en la integración:

| Entorno | URL |
|---------|-----|
| Local | `http://localhost:8000/brands/canva/callback/` |
| Producción | `https://tu-dominio.com/brands/canva/callback/` |

> Se pueden agregar múltiples redirect URIs. Agregar todas las que se usen.

---

## 3. Brand Templates en Canva

Antes de usar la API, alguien debe crear al menos una **Brand Template** en Canva:

### ¿Qué es una Brand Template?

Una Brand Template es un diseño de Canva que:
- Tiene campos marcados como "editables" (texto, imágenes)
- Está publicada para que la API la pueda encontrar
- Pertenece al brand kit de la organización Enterprise

### Cómo crear una

| Paso | Acción |
|------|--------|
| 1 | Abrir Canva y crear un diseño nuevo (post de Instagram, carrusel, story, etc.) |
| 2 | Diseñar con todos los elementos de marca (logo, colores, fuentes) |
| 3 | Marcar los elementos que la API debe rellenar como "campos de marca" |
| 4 | Publicar como Brand Template en el Brand Kit de la organización |
| 5 | Copiar el **Brand Template ID** del URL o la API |

### Templates recomendados para empezar

| Template | Tamaño | Uso |
|----------|--------|-----|
| Post Instagram | 1080×1350 (4:5) | Posts de feed individual |
| Carrusel Instagram | 1080×1350 (4:5), 7 páginas | Carruseles educativos |
| Story Instagram | 1080×1920 (9:16) | Stories |
| Reel Cover | 1080×1920 (9:16) | Thumbnail de reels |

### Campos sugeridos en cada template

Nombre los campos de forma consistente entre templates:

| Campo | Tipo | Ejemplo |
|-------|------|---------|
| `headline` | Texto | "5 Tips para..." |
| `body` | Texto | Texto principal del slide |
| `cta` | Texto | "Guardá este post" |
| `background_image` | Imagen | Foto/ilustración de fondo |
| `accent_text` | Texto | Número, dato destacado |

> **Importante**: Los nombres de los campos es lo que la API usa para rellenar. Si el campo se llama `headline` en Canva, la API envía `{"headline": {"type": "text", "text": "5 Tips para..."}}`.

---

## 4. Variables de entorno

Agregar al archivo `.env` del proyecto:

```env
# ── Canva Connect API ──────────────────────────────────
CANVA_CLIENT_ID=DAF-xxxxx               # Del Developer Portal
CANVA_CLIENT_SECRET=xxxxx               # Del Developer Portal
CANVA_REDIRECT_URI=http://localhost:8000/brands/canva/callback/
CANVA_API_BASE_URL=https://api.canva.com/rest/v1
```

### Para producción (Railway)

```
CANVA_CLIENT_ID=DAF-xxxxx
CANVA_CLIENT_SECRET=xxxxx
CANVA_REDIRECT_URI=https://tu-dominio-railway.com/brands/canva/callback/
CANVA_API_BASE_URL=https://api.canva.com/rest/v1
```

---

## 5. Rate Limits a tener en cuenta

| Endpoint | Límite | Notas |
|----------|--------|-------|
| POST general (autofill, export) | 20 req/min por usuario | Suficiente para uso normal |
| Exports por integración | 750 cada 5 min, 5000 cada 24h | Cuidado con batch masivos |
| Exports por documento | 75 cada 5 min | Relativo a un diseño específico |

**Implicación**: Con 20 req/min, podemos generar ~10 imágenes/min (cada imagen = 2 requests: autofill + export). Para carruseles multipágina, es 1 carrusel/min (2 requests total, no por slide).

---

## 6. Resumen — Checklist final

| # | Ítem | Estado |
|---|------|--------|
| 1 | Cuenta Canva Enterprise activa | ⬜ |
| 2 | Integración creada en Developer Portal | ⬜ |
| 3 | Client ID copiado | ⬜ |
| 4 | Client Secret copiado | ⬜ |
| 5 | 7 scopes habilitados en la integración | ⬜ |
| 6 | Redirect URI configurada (local + prod) | ⬜ |
| 7 | Al menos 1 Brand Template creada y publicada | ⬜ |
| 8 | Template ID anotado | ⬜ |
| 9 | Variables de entorno en `.env` | ⬜ |
| 10 | Variables de entorno en Railway (prod) | ⬜ |

> Cuando todos los ítems estén ✅, se puede empezar a implementar siguiendo [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md).

---

## Links de referencia

| Recurso | URL |
|---------|-----|
| Canva Connect API Docs | https://www.canva.dev/docs/connect/ |
| Developer Portal | https://www.canva.com/developers/ |
| Enterprise info | https://www.canva.com/enterprise/ |
| Autofill API | https://www.canva.dev/docs/connect/autofill/ |
| Export API | https://www.canva.dev/docs/connect/exports/ |
| Asset Upload API | https://www.canva.dev/docs/connect/asset-uploads/ |
| OAuth + PKCE | https://www.canva.dev/docs/connect/authentication/ |
| Scopes reference | https://www.canva.dev/docs/connect/appendix/scopes/ |
