from django.core.management import call_command
from django.test import TestCase
from Betdata.models import Outcome, Phase, Slip, SlipItem, SlipItemMarket

class SeedClientBetDataCommandTests(TestCase):
    def test_seed_command_creates_default_phases_and_outcomes(self):
        call_command("seed_client_bet_data")
        self.assertEqual(Phase.objects.count(), 5)
        self.assertEqual(Outcome.objects.count(), 10)
        self.assertTrue(Outcome.objects.filter(code="F1", phase_id=1).exists())
        self.assertTrue(Outcome.objects.filter(code="D5", phase_id=5).exists())

class SlipModelTests(TestCase):
    def test_slip_domain_models_persist(self):
        slip = Slip.objects.create(
            player_id=12,
            game_round=33,
            total_stake="25.00",
            total_possible_win="62.50",
        )
        slip_item = SlipItem.objects.create(
            slip_id=slip.id,
            bet_id=44,
            character=7,
            bet_type="SINGLE",
            option_code="F3",
            phase_start=3,
            stake="25.00",
            odds="2.50",
            possible_win="62.50",
            placed_at="2026-01-01T00:00:00Z",
        )
        link = SlipItemMarket.objects.create(
            slip_item_id=slip_item.id,
            market_id=88,
            outcome_id=5,
            phase_number=3,
            stake_portion="25.00",
        )

        self.assertEqual(slip.status, "OPEN")
        self.assertEqual(slip_item.option_code, "F3")
        self.assertEqual(link.market_id, 88)