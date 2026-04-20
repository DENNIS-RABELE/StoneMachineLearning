import random
import json
import os
from decimal import Decimal
from typing import Iterable
from pathlib import Path
import time

from django.db import transaction

from Decision.models import (
    Character,
    DecisionRound,
    DecisionRoundStatus,
    GameRound,
    MarketOdds,
    Outcome,
    PhaseCharacterMarket,
    RoundMarketOutcome,
)
from Decision.services.decision_engine import DecisionEngine
from Decision.services.market_bootstrap import PHASE_COUNT, ensure_outcomes, ensure_round_phases, sync_character_markets_for_round


ACTIVE_CHARACTER_LIMIT = 5
DEC_0 = Decimal("0")
DEC_1 = Decimal("1")


def _default_unity_settings_path() -> Path:
    microservices_dir = Path(__file__).resolve().parents[3]
    return microservices_dir / "unity_gameplay_service" / "Game2" / "StreamingAssets" / "Settings.json"


def _read_unity_game_settings(path: Path) -> dict[str, object]:
    try:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _merge_unity_players(
    existing_payload: dict[str, object],
    *,
    resolved_players: list[dict[str, object]],
) -> dict[str, object]:
    """
    Merge resolved drown phases into existing Settings.json payload.

    - Preserve existing `players` order when possible.
    - Update only matching players; keep others unchanged.
    - Append new players if they don't exist yet.
    """
    existing_players = existing_payload.get("players")
    existing_players = existing_players if isinstance(existing_players, list) else []

    def key_for(player: dict[str, object]) -> str:
        return str(player.get("playerName") or "").strip().lower()

    resolved_by_name = {
        key_for(player): player
        for player in resolved_players
        if isinstance(player, dict) and key_for(player)
    }

    merged_players: list[dict[str, object]] = []
    seen: set[str] = set()

    for existing in existing_players:
        if not isinstance(existing, dict):
            continue
        name_key = key_for(existing)
        if not name_key:
            continue

        if name_key in resolved_by_name:
            updated = dict(existing)
            updated["drownphase"] = int(resolved_by_name[name_key].get("drownphase") or 0)
            merged_players.append(updated)
            seen.add(name_key)

    for name_key, resolved in resolved_by_name.items():
        if name_key in seen:
            continue
        merged_players.append(
            {
                "playerName": resolved.get("playerName"),
                "drownphase": int(resolved.get("drownphase") or 0),
            }
        )

    merged_payload = dict(existing_payload)
    merged_payload["players"] = merged_players
    return merged_payload


def _write_unity_game_settings(*, players: list[dict[str, object]], meta: dict[str, object] | None = None) -> None:
    """
    Update Game2 StreamingAssets Settings.json with computed outcomes.

    Unity reads this file to decide which character should drown (drownphase).
    """
    raw_path = os.getenv("UNITY_GAME2_SETTINGS_PATH", "").strip()
    target_path = Path(raw_path) if raw_path else _default_unity_settings_path()

    existing_payload = _read_unity_game_settings(target_path)
    payload = _merge_unity_players(existing_payload, resolved_players=players)
    if meta:
        payload.setdefault("meta", {})
        if isinstance(payload["meta"], dict):
            payload["meta"].update(meta)
        else:
            payload["meta"] = dict(meta)
    payload.setdefault("meta", {})
    if isinstance(payload["meta"], dict):
        payload["meta"]["updated_at_ms"] = int(time.time() * 1000)
        payload["meta"]["settings_path"] = str(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        tmp_path.replace(target_path)
    except Exception:
        # Some environments (or file locks) can block atomic replace.
        # Fall back to direct overwrite.
        target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    print(f"[Decision] Wrote Unity settings: {target_path}")


def _players_from_resolved_rows(
    *,
    character_ids: list[int],
    resolved_rows: list[RoundMarketOutcome],
) -> list[dict[str, object]]:
    rows_by_character: dict[int, list[RoundMarketOutcome]] = {}
    for row in resolved_rows:
        rows_by_character.setdefault(int(row.character_id), []).append(row)

    characters = {
        int(row.id): row
        for row in Character.objects.filter(id__in=character_ids).only("id", "name")
    }

    players: list[dict[str, object]] = []
    for character_id in character_ids:
        character = characters.get(int(character_id))
        if not character:
            continue
        drown_phase = 0
        for row in rows_by_character.get(int(character_id), []):
            if row.outcome_id and getattr(row.outcome, "code", None) == "DROWN":
                drown_phase = int(row.phase_number)
                break
        players.append({"playerName": character.clean_name, "drownphase": int(drown_phase)})

    tjoli_phase = next(
        (player["drownphase"] for player in players if player["playerName"] == "Tjoli"), 0
    )
    molisana = next((player for player in players if player["playerName"] == "Molisana"), None)
    if molisana is not None and tjoli_phase > 0:
        molisana["drownphase"] = int(tjoli_phase)

    players = [p for p in players if p["playerName"] != "Tjoli"]
    return players


def _active_character_ids(limit: int = ACTIVE_CHARACTER_LIMIT) -> list[int]:
    return list(Character.objects.order_by("-id").values_list("id", flat=True)[:limit])


def _bootstrap_markets_for_round(round_obj: DecisionRound, character_ids: Iterable[int]) -> None:
    ensure_round_phases(round_obj=round_obj, phase_count=PHASE_COUNT)
    for character_id in character_ids:
        sync_character_markets_for_round(character_id=character_id, round_obj=round_obj)


def _seed_open_round_placeholders(
    client_round_id: int,
    decision_round: DecisionRound,
    character_ids: Iterable[int],
) -> int:
    markets = list(
        PhaseCharacterMarket.objects.select_related("phase")
        .filter(
            round_id=decision_round.id,
            character_id__in=character_ids,
            phase__phase_number__lte=PHASE_COUNT,
        )
        .order_by("character_id", "phase__phase_number")
    )

    created = 0
    for market in markets:
        _, was_created = RoundMarketOutcome.objects.update_or_create(
            client_round_id=client_round_id,
            market_id=market.id,
            defaults={
                "decision_round_id": decision_round.id,
                "character_id": market.character_id,
                "phase_number": market.phase.phase_number,
                "outcome_id": None,
            },
        )
        if was_created:
            created += 1
    return created


def _existing_placeholder_rows(client_round_id: int) -> list[RoundMarketOutcome]:
    return list(
        RoundMarketOutcome.objects.select_related("market__phase")
        .filter(client_round_id=client_round_id)
        .order_by("character_id", "phase_number")
    )


def _phase_market_probabilities(market_ids: list[int]) -> dict[int, dict[str, Decimal]]:
    odds_rows = (
        MarketOdds.objects.select_related("outcome")
        .filter(market_id__in=market_ids, outcome__code__in=["FLOAT", "DROWN"])
        .only("market_id", "current_odds", "outcome__code")
    )

    odds_by_market: dict[int, dict[str, Decimal]] = {}
    for row in odds_rows:
        odds_by_market.setdefault(row.market_id, {})[row.outcome.code] = Decimal(str(row.current_odds))

    probabilities: dict[int, dict[str, Decimal]] = {}
    for market_id in market_ids:
        float_odds = odds_by_market.get(market_id, {}).get("FLOAT")
        drown_odds = odds_by_market.get(market_id, {}).get("DROWN")
        if not float_odds or not drown_odds or float_odds <= DEC_0 or drown_odds <= DEC_0:
            probabilities[market_id] = {"FLOAT": Decimal("0.5"), "DROWN": Decimal("0.5")}
            continue

        float_implied = DEC_1 / float_odds
        drown_implied = DEC_1 / drown_odds
        total = float_implied + drown_implied
        if total <= DEC_0:
            probabilities[market_id] = {"FLOAT": Decimal("0.5"), "DROWN": Decimal("0.5")}
            continue

        probabilities[market_id] = {
            "FLOAT": float_implied / total,
            "DROWN": drown_implied / total,
        }
    return probabilities


def _random_no_bet_path(
    character_market_rows: list[PhaseCharacterMarket],
    outcome_ids: dict[str, int],
) -> dict[int, int | None]:
    if not character_market_rows:
        return {}

    market_ids = [market.id for market in character_market_rows]
    probabilities = _phase_market_probabilities(market_ids=market_ids)

    terminal_weights: list[float] = []
    survive_prefix = Decimal("1")
    for market in character_market_rows:
        phase_probs = probabilities.get(market.id, {"FLOAT": Decimal("0.5"), "DROWN": Decimal("0.5")})
        terminal_weight = survive_prefix * phase_probs["DROWN"]
        terminal_weights.append(float(max(terminal_weight, DEC_0)))
        survive_prefix *= phase_probs["FLOAT"]

    if not any(weight > 0 for weight in terminal_weights):
        terminal_index = random.randrange(len(character_market_rows))
    else:
        terminal_index = random.choices(range(len(character_market_rows)), weights=terminal_weights, k=1)[0]

    float_outcome_id = outcome_ids.get("FLOAT")
    drown_outcome_id = outcome_ids.get("DROWN")
    path: dict[int, int | None] = {}
    for idx, market in enumerate(character_market_rows):
        if idx < terminal_index:
            path[market.id] = float_outcome_id
        elif idx == terminal_index:
            path[market.id] = drown_outcome_id
        else:
            path[market.id] = None
    return path


def _fallback_outcome_id_for_market(
    engine: DecisionEngine,
    market_id: int,
    outcome_ids: dict[str, int],
) -> int | None:
    return outcome_ids.get(engine.tempting_outcome(market_id))


@transaction.atomic
def prepare_open_decision_round_for_client_round(client_round_id: int) -> dict[str, object]:
    placeholder_rows = _existing_placeholder_rows(client_round_id=client_round_id)
    if placeholder_rows:
        decision_round = DecisionRound.objects.select_for_update().get(pk=placeholder_rows[0].decision_round_id)
        character_ids = list(dict.fromkeys(row.character_id for row in placeholder_rows))
    else:
        decision_round = (
            DecisionRound.objects.select_for_update().filter(status=DecisionRoundStatus.OPEN).order_by("-id").first()
        )
        if decision_round is None:
            decision_round = DecisionRound.objects.create(status=DecisionRoundStatus.OPEN)
        character_ids = _active_character_ids()

    _bootstrap_markets_for_round(decision_round, character_ids)
    placeholder_count = _seed_open_round_placeholders(
        client_round_id=client_round_id,
        decision_round=decision_round,
        character_ids=character_ids,
    )

    return {
        "client_round_id": client_round_id,
        "decision_round_id": decision_round.id,
        "character_count": len(character_ids),
        "phase_count": PHASE_COUNT,
        "placeholder_count": placeholder_count,
    }


@transaction.atomic
def resolve_current_decision_round_for_client_round(client_round_id: int) -> dict[str, object]:
    placeholder_rows = _existing_placeholder_rows(client_round_id=client_round_id)
    if placeholder_rows:
        decision_round = DecisionRound.objects.select_for_update().get(pk=placeholder_rows[0].decision_round_id)
        character_ids = list(dict.fromkeys(row.character_id for row in placeholder_rows))
    else:
        decision_round = (
            DecisionRound.objects.select_for_update().filter(status=DecisionRoundStatus.OPEN).order_by("-id").first()
        )
        if decision_round is None:
            decision_round = DecisionRound.objects.create(status=DecisionRoundStatus.OPEN)

        character_ids = _active_character_ids()
        _bootstrap_markets_for_round(decision_round, character_ids)
        _seed_open_round_placeholders(
            client_round_id=client_round_id,
            decision_round=decision_round,
            character_ids=character_ids,
        )
        placeholder_rows = _existing_placeholder_rows(client_round_id=client_round_id)

    outcome_ids = ensure_outcomes()
    engine = DecisionEngine()

    markets = [row.market for row in sorted(placeholder_rows, key=lambda row: (row.character_id, row.phase_number))]
    generated = 0
    markets_by_character: dict[int, list[PhaseCharacterMarket]] = {}
    for market in markets:
        markets_by_character.setdefault(market.character_id, []).append(market)

    for character_market_rows in markets_by_character.values():
        market_summaries = {market.id: engine.market_summary(market.id) for market in character_market_rows}
        character_has_any_bets = any(
            (Decimal(summary["totals"]["FLOAT"]) > DEC_0 or Decimal(summary["totals"]["DROWN"]) > DEC_0)
            for summary in market_summaries.values()
        )

        if not character_has_any_bets:
            random_path = _random_no_bet_path(character_market_rows, outcome_ids)
            for market in character_market_rows:
                RoundMarketOutcome.objects.update_or_create(
                    client_round_id=client_round_id,
                    market_id=market.id,
                    defaults={
                        "decision_round_id": decision_round.id,
                        "character_id": market.character_id,
                        "phase_number": market.phase.phase_number,
                        "outcome_id": random_path.get(market.id),
                    },
                )
                generated += 1
            continue

        drowned_already = False
        settled_any_phase = False
        for market in character_market_rows:
            outcome_id = None
            if not drowned_already:
                summary = market_summaries[market.id]
                outcome_code = summary["recommended_outcome"]
                outcome_id = outcome_ids.get(outcome_code)
                if outcome_id is None and not settled_any_phase:
                    outcome_id = _fallback_outcome_id_for_market(engine=engine, market_id=market.id, outcome_ids=outcome_ids)
                    outcome_code = next((code for code, pk in outcome_ids.items() if pk == outcome_id), None) if outcome_id is not None else None
                if outcome_code == "DROWN":
                    drowned_already = True
                if outcome_id is not None:
                    settled_any_phase = True

            RoundMarketOutcome.objects.update_or_create(
                client_round_id=client_round_id,
                market_id=market.id,
                defaults={
                    "decision_round_id": decision_round.id,
                    "character_id": market.character_id,
                    "phase_number": market.phase.phase_number,
                    "outcome_id": outcome_id,
                },
            )
            generated += 1

        if not settled_any_phase and character_market_rows:
            first_market = character_market_rows[0]
            forced_outcome_id = _fallback_outcome_id_for_market(
                engine=engine,
                market_id=first_market.id,
                outcome_ids=outcome_ids,
            )
            if forced_outcome_id is not None:
                RoundMarketOutcome.objects.update_or_create(
                    client_round_id=client_round_id,
                    market_id=first_market.id,
                    defaults={
                        "decision_round_id": decision_round.id,
                        "character_id": first_market.character_id,
                        "phase_number": first_market.phase.phase_number,
                        "outcome_id": forced_outcome_id,
                    },
                )

    decision_round.status = DecisionRoundStatus.RESOLVED
    decision_round.save(update_fields=["status"])

    next_round = DecisionRound.objects.create(status=DecisionRoundStatus.OPEN)
    _bootstrap_markets_for_round(next_round, character_ids)

    resolved_rows_qs = (
        RoundMarketOutcome.objects.select_related("outcome")
        .filter(client_round_id=client_round_id)
        .order_by("character_id", "phase_number")
    )
    resolved_rows = list(resolved_rows_qs)
    first_resolved_code = next(
        (row.outcome.code for row in resolved_rows if row.outcome_id and row.outcome),
        "RESOLVED",
    )

    try:
        players = _players_from_resolved_rows(character_ids=character_ids, resolved_rows=resolved_rows)
        _write_unity_game_settings(players=players, meta={"client_round_id": int(client_round_id)})
    except Exception as exc:
        # Keep resolution path resilient; Unity sync is best-effort.
        print(f"[Decision] Unity Settings.json update failed: {exc}")

    return {
        "client_round_id": client_round_id,
        "decision_round_id": decision_round.id,
        "next_decision_round_id": next_round.id,
        "character_count": len(character_ids),
        "phase_count": PHASE_COUNT,
        "generated_outcomes": generated,
        "summary_result": first_resolved_code,
    }
