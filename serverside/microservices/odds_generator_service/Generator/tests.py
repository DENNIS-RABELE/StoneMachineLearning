from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from Generator import services


class GenerateOddPayloadTests(SimpleTestCase):
    def test_generate_payload_contains_all_expected_markets(self):
        payload = services.generate_odd_payload(
            {"id": 1, "name": "alpha", "stamina": 7, "control": 6, "power": 8},
            exposure_stakes={key: Decimal("0") for key in (*services.DRN_KEYS, *services.FLT_KEYS, *services.COMBO_KEYS)},
        )

        expected_keys = set((*services.DRN_KEYS, *services.FLT_KEYS, *services.COMBO_KEYS))
        self.assertEqual(set(payload.keys()), expected_keys)
        for value in payload.values():
            self.assertGreaterEqual(value, Decimal("1.01"))
            self.assertLessEqual(value, Decimal("99.99"))

    def test_higher_skill_character_gets_shorter_drn5_odds(self):
        low_skill_payload = services.generate_odd_payload(
            {"id": 1, "name": "low", "stamina": 1, "control": 1, "power": 1},
            exposure_stakes={},
        )
        high_skill_payload = services.generate_odd_payload(
            {"id": 2, "name": "high", "stamina": 10, "control": 10, "power": 10},
            exposure_stakes={},
        )

        self.assertLess(high_skill_payload["drn5"], low_skill_payload["drn5"])
        self.assertGreater(high_skill_payload["drn1"], low_skill_payload["drn1"])

    def test_exposure_shift_shortens_the_heavily_backed_selection(self):
        no_exposure = services.generate_odd_payload(
            {"id": 1, "name": "alpha", "stamina": 5, "control": 5, "power": 5},
            exposure_stakes={},
        )
        heavy_drn1_exposure = services.generate_odd_payload(
            {"id": 1, "name": "alpha", "stamina": 5, "control": 5, "power": 5},
            exposure_stakes={"drn1": Decimal("1000")},
        )

        self.assertLess(heavy_drn1_exposure["drn1"], no_exposure["drn1"])


class SyncLatestCharacterOddsTests(SimpleTestCase):
    @patch("Generator.services.transaction.atomic")
    @patch("Generator.services.BetOdds.objects")
    @patch("Generator.services._read_exposure_stakes", return_value={})
    @patch("Generator.services.httpx.Client")
    def test_sync_latest_character_odds_upserts_latest_characters(
        self,
        client_cls,
        _read_exposure_stakes,
        objects,
        atomic,
    ):
        response = MagicMock()
        response.json.return_value = {
            "results": [
                {"id": 7, "name": "seven", "stamina": 6, "control": 5, "power": 4},
                {"id": 7, "name": "seven", "stamina": 6, "control": 5, "power": 4},
                {"id": 8, "name": "eight", "stamina": 8, "control": 7, "power": 9},
            ]
        }
        client = MagicMock()
        client.get.return_value = response
        client_cls.return_value.__enter__.return_value = client

        objects.exclude.return_value.delete.return_value = (0, {})
        atomic.return_value.__enter__.return_value = None
        atomic.return_value.__exit__.return_value = None

        result = services.sync_latest_character_odds(limit=2)

        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["character_ids"], [7, 8])
        self.assertEqual(objects.update_or_create.call_count, 2)

    @patch("Generator.services.transaction.atomic")
    @patch("Generator.services.BetOdds.objects")
    @patch("Generator.services._read_exposure_stakes", return_value={})
    @patch("Generator.services.httpx.Client")
    def test_sync_latest_character_odds_falls_back_to_decision_service(
        self,
        client_cls,
        _read_exposure_stakes,
        objects,
        atomic,
    ):
        first_response = MagicMock()
        first_response.raise_for_status.side_effect = RuntimeError("gateway unavailable")

        second_response = MagicMock()
        second_response.json.return_value = {
            "results": [
                {"id": 9, "name": "nine", "stamina": 4, "control": 7, "power": 8},
            ]
        }

        client = MagicMock()
        client.get.side_effect = [first_response, second_response]
        client_cls.return_value.__enter__.return_value = client

        objects.exclude.return_value.delete.return_value = (0, {})
        atomic.return_value.__enter__.return_value = None
        atomic.return_value.__exit__.return_value = None

        result = services.sync_latest_character_odds(limit=1)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["character_ids"], [9])
        self.assertEqual(client.get.call_count, 2)
