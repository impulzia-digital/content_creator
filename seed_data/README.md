# Seed data versionada

Este directorio guarda la configuración base del negocio y el backlog editorial inicial que sí deben vivir en Git.

## Reglas

- `brand.json`: identidad, tono, paleta y defaults editoriales.
- `users.json`: usuarios mínimos para entrar al backoffice.
- `memberships.json`: vínculo usuario ↔ marca.
- `instagram_accounts.json`: opcional. Si todavía no conectaste Meta, puede ir como lista vacía.
- `briefs.json`: backlog inicial de `ContentBrief`.

## Secretos

No guardes tokens ni passwords reales en estos archivos.

Para secretos, usá `password_env` o `access_token_env` y definí la variable en `.env`.

## Comando

```bash
docker compose exec web python manage.py seed_business_data
```

Para validar sin persistir cambios:

```bash
docker compose exec web python manage.py seed_business_data --dry-run
```