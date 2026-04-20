"""Generate an exhaustive bet-option knowledge base dataset for ML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import transaction

from Decision.models import Character

from ..models import BetOptionDefinition, BetOptionKnowledgeRow


PHASES: Tuple[int, ...] = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class OptionSpec:
    option_code: str
    bet_type: str
    float_phase: Optional[int] = None
    drown_phase: Optional[int] = None


def _probability_float(character: Character, phase_number: int) -> float:
    """Matches the Monte Carlo simulator: float probability from character attributes."""
    phase_pressure = 1.0 - ((phase_number - 1) * 0.08)
    base = (
        0.18
        + (character.stamina * 0.035)
        + (character.control * 0.02)
        + (character.power * 0.015)
    )
    return max(0.08, min(0.92, base * phase_pressure))


def _phase_float_probs(character: Character) -> List[float]:
    return [float(_probability_float(character, phase)) for phase in PHASES]


def enumerate_default_options() -> List[OptionSpec]:
    """Return the full option set supported by the current virtual betting format."""
    options: List[OptionSpec] = []
    for phase in PHASES:
        options.append(OptionSpec(option_code=f"F{phase}", bet_type="float_single", float_phase=phase))
        options.append(OptionSpec(option_code=f"D{phase}", bet_type="drown_single", drown_phase=phase))
    for float_phase in PHASES[:-1]:
        for drown_phase in PHASES:
            if drown_phase <= float_phase:
                continue
            options.append(
                OptionSpec(
                    option_code=f"F{float_phase}ANDD{drown_phase}",
                    bet_type="combo",
                    float_phase=float_phase,
                    drown_phase=drown_phase,
                )
            )
    return options


def _probability_no_drown_through(phase_float_probs: List[float], phase_number: int) -> float:
    """P(no drown in phases 1..phase_number) == product(float probs for phases 1..phase_number)."""
    product = 1.0
    for idx in range(phase_number):
        product *= float(phase_float_probs[idx])
    return float(product)


def _probability_drown_at(phase_float_probs: List[float], drown_phase: int) -> float:
    """P(drown occurs exactly at drown_phase)."""
    if drown_phase < 1 or drown_phase > len(PHASES):
        return 0.0
    survive_before = _probability_no_drown_through(phase_float_probs, drown_phase - 1)
    p_float_at = float(phase_float_probs[drown_phase - 1])
    return float(survive_before * (1.0 - p_float_at))


def probability_option_wins(spec: OptionSpec, phase_float_probs: List[float]) -> float:
    """Compute P(win) for an option code, matching importer semantics."""
    if spec.bet_type == "float_single" and spec.float_phase:
        return _probability_no_drown_through(phase_float_probs, spec.float_phase)
    if spec.bet_type == "drown_single" and spec.drown_phase:
        return _probability_drown_at(phase_float_probs, spec.drown_phase)
    if spec.bet_type == "combo" and spec.float_phase and spec.drown_phase:
        if spec.drown_phase <= spec.float_phase:
            return 0.0
        # To win combo, drown must happen exactly at drown_phase (implies float before it).
        return _probability_drown_at(phase_float_probs, spec.drown_phase)
    return 0.0


def upsert_option_definitions(option_specs: Iterable[OptionSpec]) -> Dict[str, BetOptionDefinition]:
    """Create/update option catalog rows and return mapping by option_code."""
    mapping: Dict[str, BetOptionDefinition] = {}
    for spec in option_specs:
        obj, _ = BetOptionDefinition.objects.update_or_create(
            option_code=spec.option_code,
            defaults={
                "bet_type": spec.bet_type,
                "float_phase": spec.float_phase,
                "drown_phase": spec.drown_phase,
                "is_combo": spec.bet_type == "combo",
            },
        )
        mapping[spec.option_code] = obj
    return mapping


def build_knowledge_rows(
    *,
    version: str = "v1",
    overwrite: bool = False,
    limit_characters: Optional[int] = None,
) -> int:
    """Populate BetOptionKnowledgeRow for every Character x Option."""
    option_specs = enumerate_default_options()
    with transaction.atomic():
        option_map = upsert_option_definitions(option_specs)
        if overwrite:
            BetOptionKnowledgeRow.objects.filter(version=version).delete()

        queryset = Character.objects.order_by("id")
        if limit_characters:
            queryset = queryset[: int(limit_characters)]

        created_count = 0
        for character in queryset:
            probs = _phase_float_probs(character)
            for spec in option_specs:
                p_win = probability_option_wins(spec, probs)
                implied_odds = (1.0 / p_win) if p_win > 0 else None
                obj, created = BetOptionKnowledgeRow.objects.update_or_create(
                    version=version,
                    character=character,
                    option=option_map[spec.option_code],
                    defaults={
                        "phase_float_probs": probs,
                        "p_win": float(p_win),
                        "implied_fair_odds": float(implied_odds) if implied_odds is not None else None,
                        "metadata": {
                            "character": {
                                "stamina": int(character.stamina),
                                "control": int(character.control),
                                "power": int(character.power),
                            },
                        },
                    },
                )
                if created:
                    created_count += 1
                else:
                    # Count updates as well so the caller can see progress.
                    created_count += 1
    return created_count

