from django.db import migrations


def remove_game1_and_normalize_game2(apps, schema_editor):
    UnityGameConfig = apps.get_model("Gameplay", "UnityGameConfig")

    UnityGameConfig.objects.filter(build_url="/game/").delete()
    UnityGameConfig.objects.filter(name="Game 1").delete()

    game2_configs = UnityGameConfig.objects.filter(build_url="/game2/").order_by("-updated_at", "-id")
    primary = game2_configs.first()
    if primary:
        game2_configs.exclude(id=primary.id).delete()
        if primary.name != "Game 2":
            primary.name = "Game 2"
        if not primary.is_active:
            primary.is_active = True
        primary.save(update_fields=["name", "is_active", "updated_at"])
        UnityGameConfig.objects.exclude(id=primary.id).update(is_active=False)
        return

    UnityGameConfig.objects.update(is_active=False)
    UnityGameConfig.objects.create(
        name="Game 2",
        build_url="/game2/",
        is_active=True,
    )


def restore_game1_config(apps, schema_editor):
    UnityGameConfig = apps.get_model("Gameplay", "UnityGameConfig")
    if not UnityGameConfig.objects.filter(build_url="/game/").exists():
        UnityGameConfig.objects.create(
            name="Game 1",
            build_url="/game/",
            is_active=False,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("Gameplay", "0003_seed_unity_game_configs"),
    ]

    operations = [
        migrations.RunPython(remove_game1_and_normalize_game2, restore_game1_config),
    ]
