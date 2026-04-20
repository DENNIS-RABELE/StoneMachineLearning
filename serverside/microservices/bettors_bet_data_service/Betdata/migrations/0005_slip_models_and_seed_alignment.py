from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Betdata", "0004_add_slip_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Slip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("player_id", models.BigIntegerField(db_index=True)),
                ("game_round", models.PositiveIntegerField(db_index=True)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("CLOSED", "Closed"), ("SETTLED", "Settled")], db_index=True, default="OPEN", max_length=16)),
                ("total_stake", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("total_possible_win", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("placed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "client_slip",
                "ordering": ["-placed_at", "-id"],
                "constraints": [
                    models.UniqueConstraint(fields=("player_id", "game_round"), name="uniq_client_slip_player_round"),
                    models.CheckConstraint(condition=models.Q(("total_stake__gte", 0)), name="chk_client_slip_total_stake_non_negative"),
                    models.CheckConstraint(condition=models.Q(("total_possible_win__gte", 0)), name="chk_client_slip_total_possible_win_non_negative"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SlipItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slip_id", models.BigIntegerField(db_index=True)),
                ("bet_id", models.BigIntegerField(db_index=True, unique=True)),
                ("character", models.PositiveIntegerField(db_index=True)),
                ("bet_type", models.CharField(choices=[("SINGLE", "Single"), ("DOUBLE", "Double")], db_index=True, max_length=8)),
                ("option_code", models.CharField(db_index=True, max_length=16)),
                ("phase_start", models.PositiveSmallIntegerField(db_index=True)),
                ("phase_end", models.PositiveSmallIntegerField(blank=True, db_index=True, null=True)),
                ("stake", models.DecimalField(decimal_places=2, max_digits=12)),
                ("odds", models.DecimalField(decimal_places=2, max_digits=8)),
                ("possible_win", models.DecimalField(decimal_places=2, max_digits=14)),
                ("placed_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "client_slip_item",
                "ordering": ["placed_at", "id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("stake__gt", 0)), name="chk_client_slip_item_stake_gt_0"),
                    models.CheckConstraint(condition=models.Q(("odds__gt", 0)), name="chk_client_slip_item_odds_gt_0"),
                    models.CheckConstraint(condition=models.Q(("possible_win__gte", 0)), name="chk_client_slip_item_possible_win_non_negative"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SlipItemMarket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slip_item_id", models.BigIntegerField(db_index=True)),
                ("market_id", models.BigIntegerField(db_index=True)),
                ("outcome_id", models.PositiveIntegerField(db_index=True)),
                ("phase_number", models.PositiveSmallIntegerField(db_index=True)),
                ("stake_portion", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "client_slip_item_market",
                "ordering": ["slip_item_id", "phase_number", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("slip_item_id", "market_id", "outcome_id"), name="uniq_client_slip_item_market_outcome"),
                    models.CheckConstraint(condition=models.Q(("stake_portion__gt", 0)), name="chk_client_slip_item_market_stake_portion_gt_0"),
                ],
            },
        ),
    ]
