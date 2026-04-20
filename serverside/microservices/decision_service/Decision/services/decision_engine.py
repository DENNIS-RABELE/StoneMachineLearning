from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from Decision.models import MarketOdds, Outcome, PhaseCharacterMarket
from Decision.services.redis_market_store import (
    RedisMarketStoreError,
    get_market_totals,
    get_shared_character_phase_totals,
    set_market_totals,
)


DEC_0 = Decimal("0")
DEC_1 = Decimal("1")
DEC_HALF = Decimal("0.5")
ODDS_QUANT = Decimal("0.0001")
STAKE_QUANT = Decimal("0.01")
RATIO_QUANT = Decimal("0.0001")


class DecisionEngine:
    def __init__(
        self,
        house_margin: Decimal = Decimal("0.08"),
        min_odds: Decimal = Decimal("1.01"),
        max_odds: Decimal = Decimal("25.00"),
        imbalance_penalty_factor: Decimal = Decimal("1.5"),
        whale_threshold: Decimal = Decimal("500"),
        whale_penalty: Decimal = Decimal("2.0"),
    ):
        self.house_margin = house_margin
        self.min_odds = min_odds
        self.max_odds = max_odds
        self.imbalance_penalty_factor = imbalance_penalty_factor
        self.whale_threshold = whale_threshold
        self.whale_penalty = whale_penalty

    def totals_from_db(self, market_id: int) -> Dict[str, Decimal]:
        return {"FLOAT": DEC_0, "DROWN": DEC_0}

    def max_bets_from_db(self, market_id: int) -> Dict[str, Decimal]:
        rows = []
        max_bets = {"FLOAT": DEC_0, "DROWN": DEC_0}
        for row in rows:
            code = row["code"]
            if code in max_bets:
                max_bets[code] = Decimal(str(row["max_stake"]))
        return max_bets

    def _shared_totals_for_market(self, market: PhaseCharacterMarket) -> Dict[str, Decimal]:
        try:
            shared = get_shared_character_phase_totals(
                character_id=market.character_id,
                phase_number=market.phase.phase_number,
            )
            if shared["FLOAT"] > DEC_0 or shared["DROWN"] > DEC_0:
                return shared
        except RedisMarketStoreError:
            pass
        return {"FLOAT": DEC_0, "DROWN": DEC_0}

    def totals(self, market_id: int, market: PhaseCharacterMarket | None = None) -> Dict[str, Decimal]:
        try:
            cached = get_market_totals(market_id)
            if cached["FLOAT"] > DEC_0 or cached["DROWN"] > DEC_0:
                return cached
        except RedisMarketStoreError:
            pass

        if market is None:
            market = (
                PhaseCharacterMarket.objects.select_related("phase")
                .only("id", "character_id", "phase__phase_number")
                .get(pk=market_id)
            )

        shared = self._shared_totals_for_market(market)
        if shared["FLOAT"] > DEC_0 or shared["DROWN"] > DEC_0:
            try:
                set_market_totals(market_id, shared)
            except RedisMarketStoreError:
                pass
            return shared

        fresh = self.totals_from_db(market_id)
        try:
            set_market_totals(market_id, fresh)
        except RedisMarketStoreError:
            pass
        return fresh

    def stake_difference(self, totals: Dict[str, Decimal]) -> Decimal:
        return (totals["FLOAT"] - totals["DROWN"]).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)

    def odds_for_totals(self, totals: Dict[str, Decimal]) -> Dict[str, Decimal]:
        total_stake = totals["FLOAT"] + totals["DROWN"]
        if total_stake <= DEC_0:
            return {"FLOAT": Decimal("2.0000"), "DROWN": Decimal("2.0000")}

        payout_budget = total_stake * (DEC_1 - self.house_margin)
        odds = {}
        for code in ("FLOAT", "DROWN"):
            side_stake = totals[code]
            raw = self.max_odds if side_stake <= DEC_0 else payout_budget / side_stake
            clipped = min(max(raw, self.min_odds), self.max_odds)
            odds[code] = clipped.quantize(ODDS_QUANT, rounding=ROUND_HALF_UP)
        return odds

    def liabilities(self, totals: Dict[str, Decimal], odds: Dict[str, Decimal]) -> Dict[str, Decimal]:
        return {
            "FLOAT": (totals["FLOAT"] * max(odds["FLOAT"] - DEC_1, DEC_0)).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP),
            "DROWN": (totals["DROWN"] * max(odds["DROWN"] - DEC_1, DEC_0)).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP),
        }

    def imbalance_ratio(self, totals: Dict[str, Decimal]) -> Decimal:
        total = totals["FLOAT"] + totals["DROWN"]
        if total <= DEC_0:
            return DEC_HALF.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP)
        return (totals["FLOAT"] / total).quantize(RATIO_QUANT, rounding=ROUND_HALF_UP)

    def imbalance_penalties(self, totals: Dict[str, Decimal]) -> Dict[str, Decimal]:
        ratio = self.imbalance_ratio(totals)
        if Decimal("0.45") <= ratio <= Decimal("0.55"):
            return {"FLOAT": DEC_1, "DROWN": DEC_1}

        if ratio > Decimal("0.55"):
            intensity = (ratio - Decimal("0.55")) / Decimal("0.45")
            return {
                "FLOAT": (DEC_1 + (self.imbalance_penalty_factor * intensity)).quantize(RATIO_QUANT, rounding=ROUND_HALF_UP),
                "DROWN": DEC_1.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP),
            }

        intensity = (Decimal("0.45") - ratio) / Decimal("0.45")
        return {
            "FLOAT": DEC_1.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP),
            "DROWN": (DEC_1 + (self.imbalance_penalty_factor * intensity)).quantize(RATIO_QUANT, rounding=ROUND_HALF_UP),
        }

    def apply_imbalance_adjustment(
        self,
        liabilities: Dict[str, Decimal],
        totals: Dict[str, Decimal],
    ) -> Dict[str, Decimal]:
        penalties = self.imbalance_penalties(totals)
        return {
            "FLOAT": (liabilities["FLOAT"] * penalties["FLOAT"]).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP),
            "DROWN": (liabilities["DROWN"] * penalties["DROWN"]).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP),
        }

    def whale_flags(self, max_bets: Dict[str, Decimal]) -> Dict[str, bool]:
        return {
            "FLOAT": max_bets["FLOAT"] >= self.whale_threshold,
            "DROWN": max_bets["DROWN"] >= self.whale_threshold,
        }

    def apply_whale_adjustment(
        self,
        liabilities: Dict[str, Decimal],
        max_bets: Dict[str, Decimal],
    ) -> Dict[str, Decimal]:
        whales = self.whale_flags(max_bets)
        if whales["FLOAT"] and whales["DROWN"]:
            return liabilities

        adjusted = dict(liabilities)
        if whales["FLOAT"]:
            adjusted["FLOAT"] = (adjusted["FLOAT"] * self.whale_penalty).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)
        if whales["DROWN"]:
            adjusted["DROWN"] = (adjusted["DROWN"] * self.whale_penalty).quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)
        return adjusted

    def adjusted_liabilities(
        self,
        market_id: int,
        totals: Dict[str, Decimal],
        odds: Dict[str, Decimal],
        max_bets: Dict[str, Decimal] | None = None,
    ) -> Dict[str, Decimal]:
        base = self.liabilities(totals, odds)
        imbalance_adjusted = self.apply_imbalance_adjustment(base, totals)
        if max_bets is None:
            max_bets = self.max_bets_from_db(market_id)
        return self.apply_whale_adjustment(imbalance_adjusted, max_bets)

    def tempting_outcome(self, market_id: int) -> str:
        odds_rows = list(
            MarketOdds.objects.select_related("outcome")
            .filter(market_id=market_id, outcome__code__in=["FLOAT", "DROWN"])
            .only("current_odds", "outcome__code")
        )
        if not odds_rows:
            return "FLOAT"

        best_code = "FLOAT"
        best_odds = Decimal("0")
        for row in odds_rows:
            current_odds = Decimal(str(row.current_odds))
            code = row.outcome.code
            if current_odds > best_odds or (current_odds == best_odds and code == "FLOAT"):
                best_odds = current_odds
                best_code = code
        return best_code

    def recommended_outcome(
        self,
        market_id: int,
        liabilities: Dict[str, Decimal],
        totals: Dict[str, Decimal] | None = None,
    ) -> str:
        if totals is not None and (totals["FLOAT"] + totals["DROWN"]) <= DEC_0:
            return self.tempting_outcome(market_id)
        if liabilities["DROWN"] > liabilities["FLOAT"]:
            return "FLOAT"
        return "DROWN"

    def decision_snapshot(
        self,
        market_id: int,
        totals: Dict[str, Decimal],
        odds: Dict[str, Decimal],
    ) -> Dict[str, object]:
        max_bets = self.max_bets_from_db(market_id)
        base_liabilities = self.liabilities(totals, odds)
        imbalance_penalties = self.imbalance_penalties(totals)
        adjusted_liabilities = self.apply_whale_adjustment(
            self.apply_imbalance_adjustment(base_liabilities, totals),
            max_bets,
        )
        whales = self.whale_flags(max_bets)
        return {
            "has_bets": (totals["FLOAT"] + totals["DROWN"]) > DEC_0,
            "imbalance_ratio_float": str(self.imbalance_ratio(totals)),
            "imbalance_penalties": {
                "FLOAT": str(imbalance_penalties["FLOAT"]),
                "DROWN": str(imbalance_penalties["DROWN"]),
            },
            "max_bets": {
                "FLOAT": str(max_bets["FLOAT"].quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)),
                "DROWN": str(max_bets["DROWN"].quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)),
            },
            "whale_flags": whales,
            "base_liabilities": {
                "FLOAT": str(base_liabilities["FLOAT"]),
                "DROWN": str(base_liabilities["DROWN"]),
            },
            "adjusted_liabilities": {
                "FLOAT": str(adjusted_liabilities["FLOAT"]),
                "DROWN": str(adjusted_liabilities["DROWN"]),
            },
            "recommended_outcome": self.recommended_outcome(
                market_id=market_id,
                liabilities=adjusted_liabilities,
                totals=totals,
            ),
        }

    def market_summary(self, market_id: int) -> Dict[str, object]:
        market = (
            PhaseCharacterMarket.objects.select_related("phase", "character", "round")
            .get(pk=market_id)
        )
        totals = self.totals(market_id, market=market)
        odds = self.odds_for_totals(totals)
        decision = self.decision_snapshot(market_id=market_id, totals=totals, odds=odds)
        return {
            "market_id": market_id,
            "round_id": market.round_id,
            "phase_id": market.phase_id,
            "phase_number": market.phase.phase_number,
            "character_id": market.character_id,
            "character_name": market.character.name,
            "totals": {
                "FLOAT": str(totals["FLOAT"].quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)),
                "DROWN": str(totals["DROWN"].quantize(STAKE_QUANT, rounding=ROUND_HALF_UP)),
            },
            "stake_difference_float_minus_drown": str(self.stake_difference(totals)),
            "odds": {"FLOAT": str(odds["FLOAT"]), "DROWN": str(odds["DROWN"])},
            "liabilities": decision["adjusted_liabilities"],
            "base_liabilities": decision["base_liabilities"],
            "adjusted_liabilities": decision["adjusted_liabilities"],
            "imbalance_ratio_float": decision["imbalance_ratio_float"],
            "imbalance_penalties": decision["imbalance_penalties"],
            "max_bets": decision["max_bets"],
            "whale_flags": decision["whale_flags"],
            "recommended_outcome": decision["recommended_outcome"],
        }

    def sync_odds_rows(self, market_id: int, odds: Dict[str, Decimal]) -> None:
        outcomes = {
            row.code: row.id
            for row in Outcome.objects.filter(code__in=["FLOAT", "DROWN"]).only("id", "code")
        }
        for code, odd_value in odds.items():
            outcome_id = outcomes.get(code)
            if not outcome_id:
                continue
            MarketOdds.objects.update_or_create(
                market_id=market_id,
                outcome_id=outcome_id,
                defaults={"current_odds": odd_value},
            )
