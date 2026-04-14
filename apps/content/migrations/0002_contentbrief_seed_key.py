from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentbrief",
            name="seed_key",
            field=models.CharField(
                blank=True,
                help_text="Clave estable para sincronizar briefs versionados desde seed data",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="contentbrief",
            constraint=models.UniqueConstraint(
                condition=Q(seed_key__isnull=False) & ~Q(seed_key=""),
                fields=("brand", "seed_key"),
                name="content_brief_seed_key_unique",
            ),
        ),
    ]