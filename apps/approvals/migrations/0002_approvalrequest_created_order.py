from django.db import migrations, models
import apps.common.models


class Migration(migrations.Migration):

    dependencies = [
        ("approvals", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequest",
            name="created_order",
            field=models.BigIntegerField(db_index=True, default=apps.common.models.next_creation_order, editable=False),
        ),
    ]