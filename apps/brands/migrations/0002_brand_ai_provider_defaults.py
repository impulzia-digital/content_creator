from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("brands", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="ai_provider_defaults",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Overrides por capacidad/agente. Ej: "
                    '{"text": {"default": {"provider": "gemini", "model": "gemini-2.5-flash"}, '
                    '"carousel": {"model": "gemini-2.5-pro"}}, '
                    '"image": {"default": {"provider": "gemini", "model": "gemini-3-pro-image-preview"}}}'
                ),
            ),
        ),
    ]