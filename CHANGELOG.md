# Changelog

## 2026-04-15

- Documentación de integración con Canva Connect API añadida en `docs/canva-integration/`: guía completa, plan de implementación en 4 fases (Ruta Canva + Ruta Híbrida) y checklist de prerequisitos. Pendiente de cuenta Enterprise para implementar.
- Soporte de video promovido a capability de primera clase: catálogo ampliado, defaults por marca/brief y selector de provider/modelo para reels en el formulario.
- Implementados providers de video para Creatomate y Google Veo, con registro/routing real, settings dedicados y persistencia automática de assets de video y thumbnail desde `VideoAgent`.
- Backoffice endurecido para generaciones incompletas: el detalle del brief detecta reels sin asset renderizado, permite regeneración y mejora el streaming MP4 con soporte de byte ranges.
- Compatibilidad de Gemini/Veo corregida para payloads no soportados por la API actual, eliminando flags rechazados y moviendo restricciones visuales al prompt cuando aplica.

## 2026-04-14

- Seed versionada del negocio añadida con comando `seed_business_data`, migración de `seed_key` y datos iniciales de Impulzia.
- Flujo de imágenes corregido para `gpt-image-1`: soporte de payloads base64, normalización de tamaños y fallo explícito si no se generan assets útiles.
- Orquestación endurecida para reintentos y propagación de errores sin duplicar variantes.
- Backoffice corregido para renderizar bien el brief enriquecido y servir assets desde Django; publicación a Instagram ahora usa URLs presignadas cuando no hay dominio CDN propio.
- Routing IA ampliado con catálogo de modelos, overrides por marca y brief, providers Gemini e Imagen 4, y selector dinámico de modelos en el formulario de briefs.
- Compatibilidad corregida para GPT-5 con `max_completion_tokens` y para Gemini Image sin `output_mime_type` en la API nativa.
- Sistema de costos pulido para reflejar la generación vigente en brief, variante y tabla, con backfill de variantes históricas y cobertura de tests dedicada.
- Pricing de providers alineado con la documentación oficial: GPT Image usa `quality=medium` explícita y tarifas reales por modelo/tamaño, Gemini Flash-Lite corrige sus rates, Gemini Image excluye thought-images y suma tokens billables cuando la API los expone, e Imagen 4 pasa a precio plano por imagen según modelo.

## 2026-04-13

- Bootstrap completo de la plataforma de contenido para Instagram con Django, Celery, PostgreSQL y Redis.
- Implementación de modelos, admin, agentes, integraciones, publicación, middleware multi-marca y backoffice.
- Configuración de Docker, Railway, ngrok por defecto en desarrollo y documentación inicial.
- Suite de tests con pytest para modelos, agentes, integraciones y tasks; compatibilidad async corregida.
