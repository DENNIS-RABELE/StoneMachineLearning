from django.db import migrations


def seed_unity_game_configs(apps, schema_editor):
    UnityGameConfig = apps.get_model("Gameplay", "UnityGameConfig")
    if UnityGameConfig.objects.exists():
        return

    UnityGameConfig.objects.create(
        name="Game 1",
        build_url="/game/",
        is_active=True,
    )
    UnityGameConfig.objects.create(
        name="Game 2",
        build_url="/game2/",
        is_active=False,
    )


def remove_seeded_configs(apps, schema_editor):
    UnityGameConfig = apps.get_model("Gameplay", "UnityGameConfig")
    UnityGameConfig.objects.filter(name__in=["Game 1", "Game 2"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("Gameplay", "0002_unitygameplaydashboardlink"),
    ]

    operations = [
        migrations.RunPython(seed_unity_game_configs, remove_seeded_configs),
    ]
