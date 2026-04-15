from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0002_contentbrief_seed_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentbrief",
            name="ai_provider_overrides",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Overrides opcionales para este brief. Soporta nivel default o por agente. Ej: "
                    '{"text": {"default": {"provider": "gemini", "model": "gemini-2.5-pro"}}, '
                    '"image": {"default": {"provider": "gemini", "model": "gemini-3-pro-image-preview"}}}'
                ),
            ),
        ),
    ]