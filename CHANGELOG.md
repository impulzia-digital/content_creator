# Changelog

## 2026-04-14

- Seed versionada del negocio añadida con comando `seed_business_data`, migración de `seed_key` y datos iniciales de Impulzia.
- Flujo de imágenes corregido para `gpt-image-1`: soporte de payloads base64, normalización de tamaños y fallo explícito si no se generan assets útiles.
- Orquestación endurecida para reintentos y propagación de errores sin duplicar variantes.
- Backoffice corregido para renderizar bien el brief enriquecido y servir assets desde Django; publicación a Instagram ahora usa URLs presignadas cuando no hay dominio CDN propio.
- Routing IA ampliado con catálogo de modelos, overrides por marca y brief, providers Gemini e Imagen 4, y selector dinámico de modelos en el formulario de briefs.
- Compatibilidad corregida para GPT-5 con `max_completion_tokens` y para Gemini Image sin `output_mime_type` en la API nativa.
- Sistema de costos pulido para reflejar la generación vigente en brief, variante y tabla, con backfill de variantes históricas y cobertura de tests dedicada.

## 2026-04-13

- Bootstrap completo de la plataforma de contenido para Instagram con Django, Celery, PostgreSQL y Redis.
- Implementación de modelos, admin, agentes, integraciones, publicación, middleware multi-marca y backoffice.
- Configuración de Docker, Railway, ngrok por defecto en desarrollo y documentación inicial.
- Suite de tests con pytest para modelos, agentes, integraciones y tasks; compatibilidad async corregida.
