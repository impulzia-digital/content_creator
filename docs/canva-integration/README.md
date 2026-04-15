# Integración de Canva — Guía Completa

> **Estado**: Planificado — pendiente de cuenta Canva Enterprise.  
> **Última actualización**: 2026-04-15  
> **Autor**: Investigación y diseño de arquitectura completados.

---

## Índice

1. [¿Qué es y qué hace?](#qué-es-y-qué-hace)
2. [¿Por qué Canva?](#por-qué-canva)
3. [Requisitos previos](#requisitos-previos)
4. [Costos](#costos)
5. [Arquitectura — Dos rutas](#arquitectura--dos-rutas)
6. [Cómo convive con el flujo actual](#cómo-convive-con-el-flujo-actual)
7. [API de Canva — Resumen técnico](#api-de-canva--resumen-técnico)
8. [Rate Limits](#rate-limits)
9. [Limitaciones y consideraciones](#limitaciones-y-consideraciones)
10. [Documentos relacionados](#documentos-relacionados)

---

## ¿Qué es y qué hace?

Canva Connect API permite a nuestra plataforma usar **plantillas de diseño de Canva** como parte del pipeline de generación de contenido para Instagram. En vez de (o además de) generar imágenes con IA pura (OpenAI, Gemini, Imagen), podemos:

- **Rellenar plantillas** de Canva automáticamente con textos, imágenes y datos generados por IA
- **Exportar** los diseños resultantes como JPG/PNG listos para publicar
- **Combinar** imágenes generadas por IA con composiciones de marca en Canva

**Lo que Canva NO hace como API:**
- No genera imágenes desde cero (no es generativa como DALL-E)
- No crea diseños nuevos sin plantilla base
- No permite editar pixel por pixel

**Lo que Canva SÍ hace:**
- Rellena campos de texto e imagen en plantillas predefinidas (Autofill API)
- Exporta diseños en múltiples formatos (Export API)
- Sube assets para usar dentro de diseños (Asset API)
- Maneja autenticación por marca con OAuth 2.0 + PKCE

---

## ¿Por qué Canva?

| Ventaja | Detalle |
|---------|---------|
| **Branding consistente** | Las plantillas mantienen fonts, colores y layouts de marca siempre iguales |
| **No-designer friendly** | Las marcas diseñan la plantilla una vez en Canva (visual) y la API la rellena |
| **Carruseles multipágina** | UN template con N páginas = N slides de carrusel en un solo API call |
| **Composición IA + Marca** | Imagen generada por IA como fondo + overlays de marca por Canva |
| **Costo marginal $0** | La API no cobra por llamada, está incluida en la suscripción Enterprise |

---

## Requisitos previos

Ver el documento completo en [PREREQUISITES.md](PREREQUISITES.md).

**Resumen rápido:**

1. ✅ Cuenta Canva **Enterprise** (obligatoria para Autofill API)
2. ✅ Integración creada en [Canva Developer Portal](https://www.canva.com/developers/)
3. ✅ Credenciales OAuth: `Client ID` + `Client Secret`
4. ✅ Scopes configurados: `design:content:read/write`, `brandtemplate:meta:read`, `brandtemplate:content:read`, `asset:read/write`
5. ✅ Al menos una **Brand Template** creada y publicada en Canva
6. ✅ Variables de entorno configuradas en `.env`

---

## Costos

### Suscripción Canva

| Plan | Precio (USD/mes aprox) | ¿Sirve para la API? |
|------|----------------------|---------------------|
| Free | $0 | ❌ No |
| Pro | ~$8/usuario | ❌ No tiene Autofill API |
| Business | ~$10.50/usuario | ❌ No tiene Autofill API |
| **Enterprise** | **Negociable con ventas** | ✅ Sí — único plan con Autofill API |

> **Nota**: El precio de Enterprise se negocia directamente con el equipo de ventas de Canva. Contactar en [canva.com/enterprise](https://www.canva.com/enterprise/).

### Costo por llamada API

- **$0 adicional** por llamada. Las APIs están incluidas en la suscripción Enterprise.
- No hay facturación por uso de Autofill, Export ni Asset Upload.
- El único costo es la suscripción mensual/anual de Enterprise (por cantidad de seats).

### Comparativa con providers actuales

| Provider | Costo por imagen (aprox) | Tipo |
|----------|------------------------|------|
| OpenAI gpt-image-1 | $0.02–$0.19 | Generativa |
| Gemini Image | $0.02–$0.07 | Generativa |
| Imagen 4 | $0.03–$0.06 | Generativa |
| **Canva Autofill** | **$0 por llamada** | Template-based |

---

## Arquitectura — Dos rutas

### Ruta 1: Ruta Canva (100% plantillas)

```
ContentBrief
   │
   ├→ BriefEnricherAgent (igual que ahora)
   │
   ├→ ImageAgent / CarouselAgent
   │     │
   │     ├─ LLM genera campos de autofill (headline, body, CTA...)
   │     │  en vez de un prompt visual
   │     │
   │     ├─ CanvaImageProvider
   │     │     ├─ Autofill API → rellena plantilla
   │     │     ├─ Export API   → exporta JPG
   │     │     └─ Download     → descarga imagen
   │     │
   │     └─ Upload a S3 → Asset
   │
   ├→ CopyAgent (igual)
   └→ HashtagAgent (igual)
```

**Cuándo usar**: La marca tiene plantillas diseñadas y quiere consistencia visual total. No necesita imágenes generativas.

### Ruta 2: Ruta Híbrida (IA generativa + Canva compone)

```
ContentBrief
   │
   ├→ BriefEnricherAgent (igual)
   │
   ├→ ImageAgent
   │     │
   │     ├─ LLM genera prompt visual (igual que hoy)
   │     ├─ OpenAI/Gemini/Imagen genera imagen base
   │     │
   │     ├─ CanvaCompositor (paso nuevo)
   │     │     ├─ Upload imagen base a Canva
   │     │     ├─ LLM genera textos de overlay (headline, CTA)
   │     │     ├─ Autofill API → plantilla con imagen de fondo + textos
   │     │     ├─ Export API   → JPG final compuesto
   │     │     └─ Download     → descarga
   │     │
   │     └─ Upload a S3 → Asset (source=TEMPLATE)
   │
   ├→ CopyAgent (igual)
   └→ HashtagAgent (igual)
```

**Cuándo usar**: La marca quiere imágenes únicas generadas por IA pero con overlays de branding consistentes (logo, tipografía, CTA).

---

## Cómo convive con el flujo actual

Canva se integra como un **ImageProvider más** dentro del patrón existente:

```
ABC (base.py)
  └─ ImageProvider
       ├─ OpenAIImageProvider     ← ya existe
       ├─ GeminiImageProvider     ← ya existe
       ├─ ImagenProvider          ← ya existe
       └─ CanvaImageProvider      ← nuevo
```

**Lo que NO cambia:**
- El Orchestrator no cambia — es agnóstico al provider
- CopyAgent, HashtagAgent, BriefEnricherAgent — no cambian
- PublishingTask — no cambia (consume `Asset.public_url`, sin importar origen)
- El flujo de aprobación — no cambia
- Los providers existentes — no cambian (ignoran el campo `brand_id` que se añade)

**Lo que SÍ cambia:**
- `ImageGenerationRequest` recibe campo opcional `brand_id` (para resolver tokens OAuth)
- `ImageAgent` tiene branch para cuando provider es "canva"
- `CarouselAgent` tiene branch para batch autofill
- Registry, Routing y Model Catalog incluyen "canva" como opción
- Brand model tiene nuevo flag `canva_composition_enabled` para Ruta Híbrida
- Nuevos modelos: `CanvaAccount`, `CanvaTemplate`

**Selección de ruta por brief:**
- En el formulario de creación de brief, el dropdown de "Provider de imagen" mostrará "Canva" como opción
- Si se selecciona "Canva" → Ruta Canva
- Si se selecciona otro provider (OpenAI, etc.) Y la marca tiene `canva_composition_enabled=True` → Ruta Híbrida
- Si se selecciona otro provider Y la marca NO tiene composición → flujo actual sin cambios

---

## API de Canva — Resumen técnico

### Base URL
```
https://api.canva.com/rest/v1
```

### Autenticación
- **OAuth 2.0 + PKCE** (Proof Key for Code Exchange)
- Tokens por usuario/marca (no API key global)
- Access token expira, refresh token para renovar
- Redirect URI necesaria para el flujo OAuth

### Endpoints principales

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/brand-templates/{id}/dataset` | GET | Obtener campos autofillables de una plantilla |
| `/autofills` | POST | Crear job de autofill (rellenar plantilla) |
| `/autofills/{id}` | GET | Consultar estado del job de autofill |
| `/exports` | POST | Crear job de exportación (diseño → imagen) |
| `/exports/{id}` | GET | Consultar estado de la exportación |
| `/asset-uploads` | POST | Subir un asset (imagen) a Canva |
| `/asset-uploads/{id}` | GET | Consultar estado del upload |

### Flujo async con polling

Todos los jobs de Canva son **asincrónicos**:

```
1. POST /autofills           → { "job": { "id": "xxx", "status": "in_progress" } }
2. GET  /autofills/{id}      → { "job": { "status": "in_progress" } }
   ... polling con backoff exponencial ...
3. GET  /autofills/{id}      → { "job": { "status": "success", "result": { "design": { "id": "yyy" } } } }
4. POST /exports             → { "job": { "id": "zzz", "status": "in_progress" } }
5. GET  /exports/{id}        → { "job": { "status": "success", "urls": ["https://..."] } }
6. GET  https://...           → descarga la imagen (URL válida 24h)
```

### Scopes OAuth necesarios

| Scope | Propósito |
|-------|-----------|
| `design:content:read` | Leer contenido de diseños |
| `design:content:write` | Crear diseños via autofill |
| `design:meta:read` | Leer metadata de diseños |
| `brandtemplate:meta:read` | Listar plantillas de marca |
| `brandtemplate:content:read` | Leer campos de plantillas |
| `asset:read` | Leer assets subidos |
| `asset:write` | Subir assets a Canva |

---

## Rate Limits

| Endpoint | Límite |
|----------|--------|
| Creación (POST) general | 20 req/min por usuario |
| Exports por integración | 750/5min, 5000/24h |
| Exports por documento | 75/5min |

**Recomendaciones:**
- Usar backoff exponencial en polling (empezar en 1s, máximo 10s)
- No hacer polling más frecuente que 1 req/s
- Para carruseles, usar templates multipágina (1 export = N páginas) en vez de N exports separados

---

## Limitaciones y consideraciones

### Enterprise obligatorio
La API de Autofill (Brand Template Autofill) **solo está disponible en Canva Enterprise**. Sin Enterprise, los endpoints de autofill retornan 403. No hay workaround.

### Latencia
El flujo Canva tiene 3 pasos async:
- Autofill: 5-15s
- Export: 5-15s
- Download: 1-5s
- **Total: 15-35s** para Ruta Canva
- **Total: 30-60s** adicionales para Ruta Híbrida (encima de la generación IA)

Esto es más lento que generar directo con OpenAI (~10-20s total), pero produce resultados con branding perfecto.

### Templates requieren diseño manual
Cada marca necesita que alguien diseñe las plantillas en Canva antes de poder usarlas. Esto es trabajo de diseño humano, no automatizable. Sin plantillas, la Ruta Canva no funciona.

### Campos de autofill
Los campos disponibles en cada plantilla dependen de cómo se diseñó. Si la plantilla tiene un campo "headline" y otro "body", eso es lo que la API puede rellenar. No se pueden añadir campos que no existen en el diseño.

### Tokens por marca
Cada marca necesita su propia conexión OAuth con Canva. No hay un token global. Esto significa:
- Cada marca configura su conexión una vez
- Los tokens se refrescan automáticamente
- Si un token expira y no se puede refrescar, la marca queda desconectada hasta reconectar manualmente

### API version
- API v1 (estable)
- Versionado por fecha para breaking changes
- Integraciones privadas (nuestro caso) no requieren revisión de Canva

---

## Documentos relacionados

| Documento | Contenido |
|-----------|-----------|
| [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) | Plan de implementación en 4 fases con archivos, código y dependencias |
| [PREREQUISITES.md](PREREQUISITES.md) | Checklist de cuentas, configuración y setup necesario antes de codificar |
| [Canva Connect API Docs](https://www.canva.dev/docs/connect/) | Documentación oficial de la API |
| [Canva Developer Portal](https://www.canva.com/developers/) | Portal para crear integración y obtener credenciales |
| [Canva Enterprise](https://www.canva.com/enterprise/) | Info y contacto para plan Enterprise |
