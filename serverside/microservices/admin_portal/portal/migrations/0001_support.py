from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CustomerSupportUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password_hash", models.CharField(max_length=128)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "portal_customer_support_user",
                "ordering": ["full_name"],
            },
        ),
        migrations.CreateModel(
            name="SupportEnquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bettor_id", models.BigIntegerField(db_index=True)),
                ("bettor_email", models.EmailField(blank=True, max_length=254)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("account", "Account Issue"),
                            ("betting", "Betting Question"),
                            ("payment", "Payment Question"),
                            ("complaint", "Complaint"),
                            ("suggestion", "Suggestion"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=32,
                    ),
                ),
                ("subject", models.CharField(max_length=160)),
                ("message", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("answered", "Answered"), ("closed", "Closed")],
                        db_index=True,
                        default="open",
                        max_length=16,
                    ),
                ),
                ("support_response", models.TextField(blank=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "responded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="responses",
                        to="portal.customersupportuser",
                    ),
                ),
            ],
            options={
                "db_table": "portal_support_enquiry",
                "ordering": ["-updated_at", "-created_at"],
                "indexes": [
                    models.Index(fields=["bettor_id", "created_at"], name="idx_support_bettor_ts"),
                    models.Index(fields=["status", "updated_at"], name="idx_support_status_ts"),
                ],
            },
        ),
    ]
