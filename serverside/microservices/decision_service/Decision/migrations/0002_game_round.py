from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Decision", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameRound",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("round_id", models.PositiveIntegerField(unique=True)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("CLOSED", "Closed")], max_length=16)),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]

