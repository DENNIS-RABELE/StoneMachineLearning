from django.contrib import admin

from .models import BetOdds


@admin.register(BetOdds)
class BetOddsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "character_id",
        "drn1",
        "drn2",
        "drn3",
        "drn4",
        "drn5",
        "flt1",
        "flt2",
        "flt3",
        "flt4",
        "flt5",
        "flt1_and_drn2",
        "flt1_and_drn3",
        "flt1_and_drn4",
        "flt1_and_drn5",
        "flt2_and_drn3",
        "flt2_and_drn4",
        "flt2_and_drn5",
        "flt3_and_drn4",
        "flt3_and_drn5",
        "flt4_and_drn5",
        "updated_at",
    )
    search_fields = ("character_id",)
    list_filter = ("created_at", "updated_at")
