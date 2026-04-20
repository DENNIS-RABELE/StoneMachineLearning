from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Betdata", "0003_fix_trigger_recursion"),
    ]

    operations = [
        migrations.AddField(
            model_name="bet",
            name="slip_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
