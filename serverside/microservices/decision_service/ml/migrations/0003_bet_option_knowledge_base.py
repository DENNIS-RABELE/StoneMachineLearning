# Generated manually for bet option knowledge base support.

import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Decision", "0001_initial"),
        ("ml", "0002_monte_carlo_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="BetOptionDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option_code", models.CharField(db_index=True, max_length=20, unique=True)),
                (
                    "bet_type",
                    models.CharField(
                        choices=[
                            ("float_single", "Float Single"),
                            ("drown_single", "Drown Single"),
                            ("combo", "Combo"),
                        ],
                        max_length=20,
                    ),
                ),
                ("float_phase", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("drown_phase", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("is_combo", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "bet_option_definitions",
                "ordering": ["option_code"],
            },
        ),
        migrations.CreateModel(
            name="BetOptionKnowledgeRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "version",
                    models.CharField(
                        db_index=True,
                        default="v1",
                        help_text="Dataset generator version identifier",
                        max_length=40,
                    ),
                ),
                (
                    "phase_float_probs",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.FloatField(),
                        help_text="Per-phase probability of FLOAT given survival (phases 1..5)",
                        size=None,
                    ),
                ),
                ("p_win", models.FloatField(help_text="Probability the option wins")),
                (
                    "implied_fair_odds",
                    models.FloatField(blank=True, help_text="1 / p_win when p_win > 0", null=True),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bet_option_knowledge_rows",
                        to="Decision.character",
                    ),
                ),
                (
                    "option",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_rows",
                        to="ml.betoptiondefinition",
                    ),
                ),
            ],
            options={
                "db_table": "bet_option_knowledge_rows",
                "ordering": ["-generated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="betoptionknowledgerow",
            constraint=models.UniqueConstraint(
                fields=("version", "character", "option"),
                name="uniq_bet_option_knowledge_version_character_option",
            ),
        ),
        migrations.AddIndex(
            model_name="betoptionknowledgerow",
            index=models.Index(fields=["version", "option"], name="bet_option__version_8f8c0f_idx"),
        ),
        migrations.AddIndex(
            model_name="betoptionknowledgerow",
            index=models.Index(fields=["version", "character"], name="bet_option__version_f79ed0_idx"),
        ),
    ]

