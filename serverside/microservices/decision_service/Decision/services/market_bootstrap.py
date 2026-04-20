from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from django.db import transaction

from Decision.models import Character, DecisionRound, MarketOdds, Outcome, Phase, PhaseCharacterMarket
from Decision.services.redis_market_store import RedisMarketStoreError, set_market_totals


PHASE_COUNT = 5
DEC_0 = Decimal("0")
DEC_1 = Decimal("1")
MIN_ODDS = Decimal("1.01")
MAX_ODDS = Decimal("25.00")
ODDS_QUANT = Decimal("0.0001")


def ensure_outcomes() -> Dict[str, int]:
    outcome_ids = {}
    for code in (Outcome.Code.FLOAT, Outcome.Code.DROWN):
        outcome, _ = Outcome.objects.get_or_create(code=code)
        outcome_ids[code] = outcome.id
    return outcome_ids


def _normalize_probabilities(probabilities: Dict[str, Decimal]) -> Dict[str, Decimal]:
    total = sum(probabilities.values(), DEC_0)
    if total <= DEC_0:
        equal = DEC_1 / Decimal(str(len(probabilities)))
        return {key: equal for key in probabilities}
    return {key: value / total for key, value in probabilities.items()}


def _decimal_odds_from_probability(probability: Decimal) -> Decimal:
    safe_probability = max(probability, Decimal("0.0001"))
    value = DEC_1 / safe_probability
    value = min(max(value, MIN_ODDS), MAX_ODDS)
    return value.quantize(ODDS_QUANT, rounding=ROUND_HALF_UP)


def _character_skill_score(character: Character) -> Decimal:
    stamina = Decimal(str(character.stamina)) / Decimal("10")
    control = Decimal(str(character.control)) / Decimal("10")
    power = Decimal(str(character.power)) / Decimal("10")
    return (stamina * Decimal("0.35")) + (control * Decimal("0.30")) + (power * Decimal("0.35"))


def _phase_probabilities_for_character(character: Character) -> Dict[int, Dict[str, Decimal]]:
    skill = _character_skill_score(character)
    float_raw = {}
    for phase_number in range(1, PHASE_COUNT + 1):
        weight = Decimal(str(PHASE_COUNT - phase_number + 1))
        phase_skill = Decimal("0.30") + (skill * weight / Decimal(str(PHASE_COUNT)))
        float_raw[phase_number] = max(Decimal("0.05"), phase_skill)

    float_probs = _normalize_probabilities({str(key): value for key, value in float_raw.items()})
    phase_odds = {}
    for phase_number in range(1, PHASE_COUNT + 1):
        float_probability = float_probs[str(phase_number)]
        drown_probability = max(Decimal("0.05"), DEC_1 - float_probability)
        normalized = _normalize_probabilities(
            {"FLOAT": float_probability, "DROWN": drown_probability}
        )
        phase_odds[phase_number] = {
            "FLOAT": _decimal_odds_from_probability(normalized["FLOAT"]),
            "DROWN": _decimal_odds_from_probability(normalized["DROWN"]),
        }
    return phase_odds


def ensure_open_round() -> DecisionRound:
    round_obj = DecisionRound.objects.filter(status="OPEN").order_by("-id").first()
    if round_obj:
        return round_obj
    return DecisionRound.objects.create(status="OPEN")


def ensure_round_phases(round_obj: DecisionRound, phase_count: int = PHASE_COUNT) -> Dict[int, Phase]:
    phase_map = {}
    for phase_number in range(1, max(1, phase_count) + 1):
        phase, _ = Phase.objects.get_or_create(
            round_id=round_obj.id,
            phase_number=phase_number,
        )
        phase_map[phase_number] = phase
    return phase_map


@transaction.atomic
def sync_character_markets_for_round(
    character_id: int,
    round_obj: DecisionRound | None = None,
) -> Dict[str, object]:
    if round_obj is None:
        round_obj = ensure_open_round()

    character = Character.objects.get(pk=character_id)
    phase_map = ensure_round_phases(round_obj=round_obj)
    outcome_ids = ensure_outcomes()
    phase_odds = _phase_probabilities_for_character(character)

    market_ids = []
    for phase_number, phase in phase_map.items():
        market, created = PhaseCharacterMarket.objects.get_or_create(
            round_id=round_obj.id,
            phase_id=phase.id,
            character_id=character_id,
        )
        market_ids.append(market.id)
        if created:
            try:
                set_market_totals(market.id, {"FLOAT": DEC_0, "DROWN": DEC_0})
            except RedisMarketStoreError:
                pass

        for code, odd_value in phase_odds[phase_number].items():
            outcome_id = outcome_ids.get(code)
            if not outcome_id:
                continue
            MarketOdds.objects.update_or_create(
                market_id=market.id,
                outcome_id=outcome_id,
                defaults={"current_odds": odd_value},
            )

    return {"round_id": round_obj.id, "market_ids": market_ids}
