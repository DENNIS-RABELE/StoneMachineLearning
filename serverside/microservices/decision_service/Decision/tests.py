from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from Decision.models import (
    Character,
    DecisionRound,
    DecisionRoundStatus,
    GameRound,
    MarketOdds,
    Outcome,
    PhaseCharacterMarket,
    RoundMarketOutcome,
    RoundStatus,
)
from Decision.round_lifecycle import (
    GAMEPLAY_START_DELAY_SECONDS,
    ROUND_DURATION_SECONDS,
    STATS_WINDOW_SECONDS,
    _gameplay_should_be_running,
    progress_round_if_due,
)
from Decision.services.decision_engine import DecisionEngine
from Decision.services.market_bootstrap import PHASE_COUNT, sync_character_markets_for_round
from Decision.services.round_outcome_service import (
    prepare_open_decision_round_for_client_round,
    resolve_current_decision_round_for_client_round,
)


class DecisionEngineTests(SimpleTestCase):
    def test_odds_for_balanced_totals_returns_house_adjusted_even_market(self):
        engine = DecisionEngine()
        odds = engine.odds_for_totals({"FLOAT": Decimal("100"), "DROWN": Decimal("100")})
        self.assertEqual(odds["FLOAT"], Decimal("1.8400"))
        self.assertEqual(odds["DROWN"], Decimal("1.8400"))


class DecisionBootstrapTests(TestCase):
    def test_sync_character_markets_for_round_creates_five_markets_and_odds(self):
        character = Character.objects.create(name="alpha", stamina=7, control=6, power=8)

        result = sync_character_markets_for_round(character_id=character.id)

        self.assertTrue(DecisionRound.objects.filter(id=result["round_id"]).exists())
        self.assertEqual(Outcome.objects.count(), 2)
        self.assertEqual(PhaseCharacterMarket.objects.filter(character=character).count(), PHASE_COUNT)
        self.assertEqual(MarketOdds.objects.filter(market__character=character).count(), PHASE_COUNT * 2)


class DecisionRoundOutcomeTests(TestCase):
    @patch("Decision.services.round_outcome_service._active_character_ids")
    @patch("Decision.services.round_outcome_service.random.choices", return_value=[1])
    @patch("Decision.services.round_outcome_service.random.randrange", return_value=1)
    def test_prepare_and_resolve_round_generate_outcomes(self, _randrange, _choices, active_character_ids):
        character = Character.objects.create(name="beta", stamina=5, control=5, power=5)
        active_character_ids.return_value = [character.id]

        prepared = prepare_open_decision_round_for_client_round(client_round_id=123)
        resolved = resolve_current_decision_round_for_client_round(client_round_id=123)

        self.assertEqual(prepared["character_count"], 1)
        self.assertEqual(resolved["generated_outcomes"], PHASE_COUNT)
        self.assertTrue(RoundMarketOutcome.objects.filter(client_round_id=123, character=character).exists())
        self.assertTrue(
            DecisionRound.objects.filter(id=resolved["decision_round_id"], status=DecisionRoundStatus.RESOLVED).exists()
        )
        self.assertTrue(
            DecisionRound.objects.filter(id=resolved["next_decision_round_id"], status=DecisionRoundStatus.OPEN).exists()
        )


class RoundLifecycleTests(TestCase):
    @patch("Decision.round_lifecycle.get_global_gameplay_state")
    @patch("Decision.round_lifecycle.start_gameplay")
    @patch("Decision.round_lifecycle.stop_gameplay")
    @patch("Decision.round_lifecycle._notify_betdata_sync")
    @patch("Decision.round_lifecycle.clear_round_state")
    @patch("Decision.round_lifecycle.resolve_current_decision_round_for_client_round")
    @patch("Decision.round_lifecycle.prepare_open_decision_round_for_client_round")
    def test_progress_round_if_due_closes_and_opens_round(
        self,
        prepare_open_round,
        resolve_round,
        clear_round_state,
        notify_sync,
        stop_gameplay,
        start_gameplay,
        get_global_gameplay_state,
    ):
        now_round = GameRound.objects.create(
            round_id=1,
            status=RoundStatus.OPEN,
            start_time=timezone.now() - timedelta(minutes=10),
        )
        get_global_gameplay_state.return_value = type(
            "State",
            (),
            {"status": "STOPPED", "max_ticks": 0},
        )()
        resolve_round.return_value = {
            "decision_round_id": 10,
            "next_decision_round_id": 11,
            "generated_outcomes": 5,
            "summary_result": "FLOAT",
        }

        with patch("Decision.round_lifecycle._seconds_elapsed_from_start", return_value=999):
            result = progress_round_if_due()

        now_round.refresh_from_db()
        self.assertEqual(now_round.status, RoundStatus.CLOSED)
        self.assertEqual(result["summary_result"], "FLOAT")
        self.assertEqual(GameRound.objects.filter(status=RoundStatus.OPEN).count(), 1)

    def test_gameplay_window_starts_when_countdown_hits_00_30(self):
        remaining_at_00_30 = GAMEPLAY_START_DELAY_SECONDS
        self.assertTrue(
            _gameplay_should_be_running(
                elapsed=max(0, ROUND_DURATION_SECONDS - remaining_at_00_30),
                remaining=remaining_at_00_30,
            )
        )

    @patch("Decision.round_lifecycle.get_global_gameplay_state")
    @patch("Decision.round_lifecycle.start_gameplay")
    @patch("Decision.round_lifecycle.stop_gameplay")
    def test_progress_round_if_due_stops_gameplay_when_countdown_hits_02_00(
        self,
        stop_gameplay,
        start_gameplay,
        get_global_gameplay_state,
    ):
        GameRound.objects.create(
            round_id=1,
            status=RoundStatus.OPEN,
            start_time=timezone.now(),
        )
        get_global_gameplay_state.return_value = type(
            "State",
            (),
            {"status": "RUNNING", "max_ticks": max(0, ROUND_DURATION_SECONDS - GAMEPLAY_START_DELAY_SECONDS - STATS_WINDOW_SECONDS)},
        )()

        elapsed_at_02_00_remaining = max(0, ROUND_DURATION_SECONDS - STATS_WINDOW_SECONDS)
        with patch("Decision.round_lifecycle._seconds_elapsed_from_start", return_value=elapsed_at_02_00_remaining):
            result = progress_round_if_due()

        self.assertEqual(result["action"], "noop")
        stop_gameplay.assert_called_once()
        start_gameplay.assert_not_called()

    def test_gameplay_window_keeps_running_after_round_rollover(self):
        elapsed_just_after_round_open = 10
        remaining = ROUND_DURATION_SECONDS - elapsed_just_after_round_open
        self.assertTrue(
            _gameplay_should_be_running(
                elapsed=elapsed_just_after_round_open,
                remaining=remaining,
            )
        )
