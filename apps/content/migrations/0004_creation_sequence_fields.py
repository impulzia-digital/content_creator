from django.db import migrations, models
import apps.common.models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0003_contentbrief_ai_provider_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentrun",
            name="created_order",
            field=models.BigIntegerField(db_index=True, default=apps.common.models.next_creation_order, editable=False),
        ),
        migrations.AddField(
            model_name="contentbrief",
            name="created_order",
            field=models.BigIntegerField(db_index=True, default=apps.common.models.next_creation_order, editable=False),
        ),
        migrations.AddField(
            model_name="contentvariant",
            name="created_order",
            field=models.BigIntegerField(db_index=True, default=apps.common.models.next_creation_order, editable=False),
        ),
    ]