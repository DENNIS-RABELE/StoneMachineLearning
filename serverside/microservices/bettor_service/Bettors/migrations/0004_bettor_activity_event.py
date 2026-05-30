from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Bettors", "0003_alter_bettors_id_alter_demomoney_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="BettorActivityEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("bettor_id", models.BigIntegerField(db_index=True)),
                ("event_type", models.CharField(db_index=True, max_length=32)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": "bettor_activity_event",
                "indexes": [
                    models.Index(fields=["bettor_id", "created_at"], name="idx_bettor_activity_user_ts"),
                    models.Index(fields=["event_type", "created_at"], name="idx_bettor_activity_type_ts"),
                ],
            },
        ),
    ]
