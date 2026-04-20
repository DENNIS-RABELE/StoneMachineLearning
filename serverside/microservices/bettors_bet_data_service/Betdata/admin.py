from django.contrib import admin
from Betdata.models import (
    Bet, HouseWallet, Outcome, Phase, PlayerWallet,
    Slip, SlipItem, SlipItemMarket, WalletTransaction,
)

@admin.register(PlayerWallet)
class PlayerWalletAdmin(admin.ModelAdmin):
    list_display = ("player_id", "balance", "updated_at")
    search_fields = ("player_id",)
    ordering = ("player_id",)
    list_per_page = 50

@admin.register(HouseWallet)
class HouseWalletAdmin(admin.ModelAdmin):
    list_display = ("id", "balance", "updated_at")

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "tx_type", "amount", "from_account", "to_account", "player_id", "game_round_id", "bet_id", "created_at")
    list_filter = ("tx_type", "from_account", "to_account", "created_at")
    search_fields = ("player_id", "note", "bet_id", "game_round_id")
    ordering = ("-created_at", "-id")
    date_hierarchy = "created_at"
    list_per_page = 50

@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("id", "player_id", "character", "game_round", "status", "bet_type", "option_code", "stake", "odds", "placed_at")
    list_filter = ("status", "bet_type", "placed_at")
    search_fields = ("player_id", "option_code", "game_round")
    ordering = ("-placed_at", "-id")
    date_hierarchy = "placed_at"
    list_per_page = 100

@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("number", "name")
    ordering = ("number",)

@admin.register(Outcome)
class OutcomeAdmin(admin.ModelAdmin):
    list_display = ("id", "external_outcome_id", "phase_id", "kind", "code", "label")
    list_filter = ("kind", "phase_id")
    search_fields = ("code", "label")
    ordering = ("external_outcome_id",)
    list_per_page = 50

@admin.register(Slip)
class SlipAdmin(admin.ModelAdmin):
    list_display = ("id", "player_id", "game_round", "status", "total_stake", "total_possible_win", "placed_at")
    list_filter = ("status", "placed_at")
    search_fields = ("player_id", "game_round")
    ordering = ("-placed_at", "-id")
    date_hierarchy = "placed_at"
    list_per_page = 50

@admin.register(SlipItem)
class SlipItemAdmin(admin.ModelAdmin):
    list_display = ("id", "slip_id", "bet_id", "character", "option_code", "stake", "possible_win", "placed_at")
    list_filter = ("bet_type", "placed_at")
    search_fields = ("slip_id", "bet_id", "option_code", "character")
    ordering = ("-placed_at", "-id")
    date_hierarchy = "placed_at"
    list_per_page = 100

@admin.register(SlipItemMarket)
class SlipItemMarketAdmin(admin.ModelAdmin):
    list_display = ("id", "slip_item_id", "market_id", "outcome_id", "phase_number", "stake_portion")
    list_filter = ("phase_number",)
    search_fields = ("slip_item_id", "market_id", "outcome_id")
    ordering = ("slip_item_id", "phase_number", "id")
    list_per_page = 100