from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def clear_legacy_support_user_links(apps, schema_editor):
    SupportEnquiry = apps.get_model("portal", "SupportEnquiry")
    SupportEnquiry.objects.update(responded_by=None)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0001_support"),
    ]

    operations = [
        migrations.RunPython(clear_legacy_support_user_links, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supportenquiry",
            name="responded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="support_responses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name="CustomerSupportUser")],
            database_operations=[],
        ),
    ]
