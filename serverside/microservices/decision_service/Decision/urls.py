from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    BetViewSet,
    RoundViewSet,
    market_summary,
    latest_characters,
    phase_bet_summary,
    realtime_bets,
    round_timer,
    current_bets_by_character,
)

router = DefaultRouter()
router.register(r'bets', BetViewSet, basename='bet')
router.register(r'rounds', RoundViewSet, basename='round')

# Include routed URLs from DRF
urlpatterns = router.urls + [
    # Legacy endpoints (kept for compatibility)
    path("api/bets/realtime/", realtime_bets, name="realtime-bets"),
    path("api/bets/phase-summary/", phase_bet_summary, name="phase-bet-summary"),
    path("api/round/timer/", round_timer, name="round-timer"),
    path("api/bets/by-character/", current_bets_by_character, name="bets-by-character"),
    path("api/characters/latest/", latest_characters, name="latest-characters"),
    path("api/markets/<int:market_id>/summary/", market_summary, name="market-summary"),
    # Preferred routes (no double /api prefix)
    path("characters/latest/", latest_characters, name="latest-characters-v2"),
]
