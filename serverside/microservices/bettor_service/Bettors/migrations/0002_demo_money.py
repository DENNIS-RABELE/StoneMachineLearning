from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Bettors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemoMoney",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.BigIntegerField(unique=True)),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("1000.00"), max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "demo_money",
            },
        ),
    ]

