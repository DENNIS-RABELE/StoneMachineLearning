# Generated manually for per-round betting snapshot support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ml", "0003_bet_option_knowledge_base"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoundBettingSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("round_id", models.PositiveIntegerField(db_index=True)),
                (
                    "game_round_pk",
                    models.PositiveIntegerField(
                        blank=True,
                        db_index=True,
                        help_text="Decision.GameRound primary key when available",
                        null=True,
                    ),
                ),
                ("captured_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("total_pool", models.FloatField(default=0.0)),
                ("total_bets", models.PositiveIntegerField(default=0)),
                ("top_characters", models.JSONField(blank=True, default=list)),
                ("top_phases_live", models.JSONField(blank=True, default=list)),
                ("top_options", models.JSONField(blank=True, default=list)),
                ("top_combos", models.JSONField(blank=True, default=list)),
                ("top_phases_selected", models.JSONField(blank=True, default=list)),
                ("thresholds", models.JSONField(blank=True, default=dict)),
                ("source", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "db_table": "round_betting_snapshots",
                "ordering": ["-captured_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="roundbettingsnapshot",
            constraint=models.UniqueConstraint(
                fields=("round_id", "captured_at"),
                name="uniq_round_betting_snapshot_round_captured_at",
            ),
        ),
    ]

