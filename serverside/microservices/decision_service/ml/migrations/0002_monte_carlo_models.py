# Generated manually for Monte Carlo bootstrap knowledge base support.

import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ml", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonteCarloSimulationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True)),
                ("random_seed", models.PositiveIntegerField(default=42)),
                ("rounds_simulated", models.PositiveIntegerField(default=0)),
                ("bettors_simulated", models.PositiveIntegerField(default=0)),
                ("characters_per_round", models.PositiveSmallIntegerField(default=5)),
                (
                    "strategies_used",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=100),
                        default=list,
                        help_text="Strategy names used in this simulation run",
                        size=None,
                    ),
                ),
                ("average_roi", models.FloatField(default=0.0)),
                ("average_win_rate", models.FloatField(default=0.0)),
                ("total_stake", models.FloatField(default=0.0)),
                ("total_payout", models.FloatField(default=0.0)),
                ("knowledge_base", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "monte_carlo_simulation_runs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MonteCarloStrategyInsight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("strategy_name", models.CharField(max_length=100)),
                ("sample_size", models.PositiveIntegerField(default=0)),
                ("average_roi", models.FloatField(default=0.0)),
                ("average_win_rate", models.FloatField(default=0.0)),
                ("expected_profit", models.FloatField(default=0.0)),
                ("profit_variance", models.FloatField(default=0.0)),
                ("average_stake", models.FloatField(default=0.0)),
                ("top_character_name", models.CharField(blank=True, max_length=255)),
                ("top_character_share", models.FloatField(default=0.0)),
                ("strategy_metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "simulation_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="strategy_insights",
                        to="ml.montecarlosimulationrun",
                    ),
                ),
            ],
            options={
                "db_table": "monte_carlo_strategy_insights",
                "ordering": ["-average_roi", "strategy_name"],
                "unique_together": {("simulation_run", "strategy_name")},
            },
        ),
    ]
