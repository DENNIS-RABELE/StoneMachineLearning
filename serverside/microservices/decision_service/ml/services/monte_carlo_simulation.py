"""Monte Carlo simulation engine for generating a bootstrap betting knowledge base."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, pvariance
from typing import Dict, List, Sequence

from Decision.models import Character

from ..models import MonteCarloSimulationRun, MonteCarloStrategyInsight


STRATEGIES = (
    "random_balanced",
    "float_chaser",
    "drown_hunter",
    "value_hunter",
    "combo_hunter",
)
PHASES = (1, 2, 3, 4, 5)


@dataclass
class SimulatedBet:
    bettor_id: str
    strategy_name: str
    character_id: int
    character_name: str
    round_id: int
    amount: float
    bet_type: str
    outcome: str
    payout: float


class MonteCarloKnowledgeBaseBuilder:
    """Run offline simulations using the local character pool."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.random = random.Random(seed)

    def _probability_float(self, character: Character, phase_number: int) -> float:
        """Derive a float probability from character attributes and phase pressure."""
        phase_pressure = 1.0 - ((phase_number - 1) * 0.08)
        base = (
            0.18
            + (character.stamina * 0.035)
            + (character.control * 0.02)
            + (character.power * 0.015)
        )
        return max(0.08, min(0.92, base * phase_pressure))

    def _simulate_round_outcomes(self, characters: Sequence[Character]) -> Dict[int, Dict[int, str | None]]:
        """Generate resolved phase outcomes for each character in a round."""
        round_outcomes: Dict[int, Dict[int, str | None]] = {}
        for character in characters:
            phase_outcomes: Dict[int, str | None] = {}
            drowned = False
            for phase_number in PHASES:
                if drowned:
                    phase_outcomes[phase_number] = None
                    continue
                prob_float = self._probability_float(character, phase_number)
                resolved = "FLOAT" if self.random.random() <= prob_float else "DROWN"
                phase_outcomes[phase_number] = resolved
                if resolved == "DROWN":
                    drowned = True
            round_outcomes[character.id] = phase_outcomes
        return round_outcomes

    def _choose_bet_option(self, strategy_name: str, character: Character) -> tuple[str, str]:
        """Return an option code and normalized bet_type label."""
        if strategy_name == "float_chaser":
            phase = self.random.choice(PHASES)
            return f"F{phase}", "float_single"
        if strategy_name == "drown_hunter":
            phase = self.random.choice(PHASES)
            return f"D{phase}", "drown_single"
        if strategy_name == "combo_hunter":
            float_phase = self.random.choice(PHASES[:-1])
            drown_phase = self.random.choice([phase for phase in PHASES if phase > float_phase])
            return f"F{float_phase}ANDD{drown_phase}", "combo"
        if strategy_name == "value_hunter":
            if character.power >= character.stamina:
                phase = self.random.choice(PHASES[:3])
                return f"D{phase}", "drown_single"
            phase = self.random.choice(PHASES[2:])
            return f"F{phase}", "float_single"

        phase = self.random.choice(PHASES)
        prefix = "F" if self.random.random() < 0.5 else "D"
        return f"{prefix}{phase}", "float_single" if prefix == "F" else "drown_single"

    def _bet_wins(self, option_code: str, resolved: Dict[int, str | None]) -> bool | None:
        option = option_code.upper()
        if option.startswith("F") and "ANDD" not in option:
            phase = int(option[1])
            actual = resolved.get(phase)
            if actual is None:
                return None
            return actual == "FLOAT"
        if option.startswith("D") and "ANDD" not in option:
            phase = int(option[1])
            actual = resolved.get(phase)
            if actual is None:
                return None
            return actual == "DROWN"
        if option.startswith("F") and "ANDD" in option:
            float_phase_str, drown_phase_str = option[1:].split("ANDD", 1)
            float_phase = int(float_phase_str)
            drown_phase = int(drown_phase_str)
            float_actual = resolved.get(float_phase)
            drown_actual = resolved.get(drown_phase)
            if float_actual is None or drown_actual is None:
                return None
            return float_actual == "FLOAT" and drown_actual == "DROWN"
        return None

    def _stake_amount(self, strategy_name: str) -> float:
        if strategy_name == "combo_hunter":
            return round(self.random.uniform(12, 28), 2)
        if strategy_name == "value_hunter":
            return round(self.random.uniform(8, 18), 2)
        if strategy_name == "float_chaser":
            return round(self.random.uniform(5, 14), 2)
        if strategy_name == "drown_hunter":
            return round(self.random.uniform(5, 16), 2)
        return round(self.random.uniform(4, 12), 2)

    def _odds_multiplier(self, option_code: str) -> float:
        option = option_code.upper()
        if "ANDD" in option:
            return round(self.random.uniform(4.0, 7.5), 2)
        if option.startswith("D"):
            return round(self.random.uniform(2.6, 5.4), 2)
        return round(self.random.uniform(1.8, 4.6), 2)

    def run(
        self,
        run_name: str,
        rounds: int,
        bettors: int,
        characters_per_round: int = 5,
    ) -> Dict[str, object]:
        """Run a Monte Carlo session and persist strategy insights."""
        character_pool = list(Character.objects.order_by("-created_at", "-id")[: max(characters_per_round, 5)])
        if len(character_pool) < 2:
            raise ValueError("Need at least 2 characters to run Monte Carlo simulations.")

        bettors_per_strategy = max(1, bettors // len(STRATEGIES))
        bettor_strategies: Dict[str, str] = {}
        bettor_ids: List[str] = []
        for strategy_name in STRATEGIES:
            for idx in range(bettors_per_strategy):
                bettor_id = f"sim_{strategy_name}_{idx + 1:04d}"
                bettor_ids.append(bettor_id)
                bettor_strategies[bettor_id] = strategy_name
        while len(bettor_ids) < bettors:
            strategy_name = STRATEGIES[len(bettor_ids) % len(STRATEGIES)]
            bettor_id = f"sim_{strategy_name}_{len(bettor_ids) + 1:04d}"
            bettor_ids.append(bettor_id)
            bettor_strategies[bettor_id] = strategy_name

        all_bets: List[SimulatedBet] = []
        strategy_profit_map: Dict[str, List[float]] = defaultdict(list)
        strategy_win_map: Dict[str, List[float]] = defaultdict(list)
        strategy_stake_map: Dict[str, List[float]] = defaultdict(list)
        strategy_character_map: Dict[str, Counter] = defaultdict(Counter)

        for round_id in range(1, rounds + 1):
            active_characters = self.random.sample(
                character_pool,
                k=min(characters_per_round, len(character_pool)),
            )
            resolved_map = self._simulate_round_outcomes(active_characters)

            for bettor_id in bettor_ids:
                strategy_name = bettor_strategies[bettor_id]
                picks_this_round = 1 if strategy_name != "combo_hunter" else self.random.choice((1, 2))
                for _ in range(picks_this_round):
                    character = self.random.choice(active_characters)
                    option_code, bet_type = self._choose_bet_option(strategy_name, character)
                    amount = self._stake_amount(strategy_name)
                    odds = self._odds_multiplier(option_code)
                    did_win = self._bet_wins(option_code, resolved_map[character.id])
                    payout = round(amount * odds, 2) if did_win else 0.0
                    outcome = "win" if did_win else "loss"

                    all_bets.append(
                        SimulatedBet(
                            bettor_id=bettor_id,
                            strategy_name=strategy_name,
                            character_id=character.id,
                            character_name=character.clean_name,
                            round_id=round_id,
                            amount=amount,
                            bet_type=bet_type,
                            outcome=outcome,
                            payout=payout,
                        )
                    )

                    strategy_profit_map[strategy_name].append(round(payout - amount, 2))
                    strategy_win_map[strategy_name].append(1.0 if did_win else 0.0)
                    strategy_stake_map[strategy_name].append(amount)
                    strategy_character_map[strategy_name][character.clean_name] += 1

        histories: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for bet in all_bets:
            histories[bet.bettor_id].append(
                {
                    "amount": bet.amount,
                    "bet_type": bet.bet_type,
                    "outcome": bet.outcome,
                    "payout": bet.payout,
                    "round_id": bet.round_id,
                }
            )

        total_stake = round(sum(bet.amount for bet in all_bets), 2)
        total_payout = round(sum(bet.payout for bet in all_bets), 2)
        average_roi = round(((total_payout - total_stake) / total_stake) * 100, 4) if total_stake else 0.0
        average_win_rate = round(mean([1.0 if bet.outcome == "win" else 0.0 for bet in all_bets]) if all_bets else 0.0, 4)

        simulation_run = MonteCarloSimulationRun.objects.create(
            name=run_name,
            description="Bootstrap Monte Carlo knowledge base for virtual betting strategies",
            random_seed=self.seed,
            rounds_simulated=rounds,
            bettors_simulated=len(bettor_ids),
            characters_per_round=min(characters_per_round, len(character_pool)),
            strategies_used=list(STRATEGIES),
            average_roi=average_roi,
            average_win_rate=average_win_rate,
            total_stake=total_stake,
            total_payout=total_payout,
            knowledge_base={
                "generated_bets": len(all_bets),
                "bettor_histories": len(histories),
                "top_strategies_by_roi": sorted(
                    [
                        {
                            "strategy": strategy_name,
                            "average_roi": round(
                                (
                                    sum(strategy_profit_map[strategy_name]) /
                                    max(sum(strategy_stake_map[strategy_name]), 1e-9)
                                ) * 100,
                                4,
                            ),
                        }
                        for strategy_name in STRATEGIES
                    ],
                    key=lambda row: row["average_roi"],
                    reverse=True,
                ),
            },
        )

        for strategy_name in STRATEGIES:
            profit_samples = strategy_profit_map[strategy_name]
            stake_samples = strategy_stake_map[strategy_name]
            top_character_name = ""
            top_character_share = 0.0
            if strategy_character_map[strategy_name]:
                top_character_name, picks = strategy_character_map[strategy_name].most_common(1)[0]
                top_character_share = round(picks / max(sum(strategy_character_map[strategy_name].values()), 1) * 100, 2)

            total_strategy_stake = sum(stake_samples)
            average_strategy_roi = round(
                (sum(profit_samples) / total_strategy_stake) * 100,
                4,
            ) if total_strategy_stake else 0.0

            MonteCarloStrategyInsight.objects.create(
                simulation_run=simulation_run,
                strategy_name=strategy_name,
                sample_size=len(profit_samples),
                average_roi=average_strategy_roi,
                average_win_rate=round(mean(strategy_win_map[strategy_name]) if strategy_win_map[strategy_name] else 0.0, 4),
                expected_profit=round(mean(profit_samples) if profit_samples else 0.0, 4),
                profit_variance=round(pvariance(profit_samples) if len(profit_samples) > 1 else 0.0, 4),
                average_stake=round(mean(stake_samples) if stake_samples else 0.0, 4),
                top_character_name=top_character_name,
                top_character_share=top_character_share,
                strategy_metadata={
                    "character_preferences": dict(strategy_character_map[strategy_name].most_common(5)),
                },
            )

        return {
            "simulation_run": simulation_run,
            "bettor_histories": histories,
            "strategy_summaries": list(simulation_run.strategy_insights.values()),
        }
