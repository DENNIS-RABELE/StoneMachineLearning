from django.contrib import admin

from .models import (
    Bet_decision,
    Character,
    DecisionRound,
    GameRound,
    MarketOdds,
    Outcome,
    Phase,
    PhaseCharacterMarket,
    RoundMarketOutcome,
)


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "stamina",
        "control",
        "power",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("name",)
    ordering = ("-created_at",)


@admin.register(Bet_decision)
class BetDecisionAdmin(admin.ModelAdmin):
    list_display = ("id", "round_result", "created_at")
    ordering = ("-created_at",)


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = ("id", "round_id", "status", "start_time", "end_time", "created_at")
    list_filter = ("status", "created_at")
    ordering = ("-round_id",)


@admin.register(DecisionRound)
class DecisionRoundAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_at")
    list_filter = ("status", "created_at")
    ordering = ("-id",)


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("id", "round", "phase_number")
    list_filter = ("round_id",)
    ordering = ("round_id", "phase_number")


@admin.register(Outcome)
class OutcomeAdmin(admin.ModelAdmin):
    list_display = ("id", "code")
    search_fields = ("code",)


@admin.register(PhaseCharacterMarket)
class PhaseCharacterMarketAdmin(admin.ModelAdmin):
    list_display = ("id", "round", "phase", "character")
    list_filter = ("round_id", "phase_id", "character_id")
    search_fields = ("character__name",)


@admin.register(MarketOdds)
class MarketOddsAdmin(admin.ModelAdmin):
    list_display = ("market", "outcome", "current_odds")
    list_filter = ("outcome__code",)


@admin.register(RoundMarketOutcome)
class RoundMarketOutcomeAdmin(admin.ModelAdmin):
    list_display = ("client_round_id", "decision_round", "character", "phase_number", "outcome", "generated_at")
    list_filter = ("decision_round_id", "phase_number", "outcome__code")
    search_fields = ("character__name",)
