from django.contrib import admin
from .models import BettorActivityEvent, Bettors, DemoMoney

# Register your models here.

@admin.register(Bettors)
class BettorClient(admin.ModelAdmin):
    list_display = (
        "id",
        "firstname",
        "lastname",
        "date_of_birth",
        "nationality",
        "id_number",
        "physical_address",
        "email"
        )
    list_filter = ("id",)
    search_fields = ("id_number",)
    ordering = ("-id",)


@admin.register(DemoMoney)
class DemoMoneyAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "amount", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("user_id",)
    ordering = ("-updated_at",)


@admin.register(BettorActivityEvent)
class BettorActivityEventAdmin(admin.ModelAdmin):
    list_display = ("id", "bettor_id", "event_type", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("bettor_id", "event_type")
    readonly_fields = ("bettor_id", "event_type", "metadata", "created_at")
    ordering = ("-created_at",)

