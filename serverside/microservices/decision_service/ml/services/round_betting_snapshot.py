"""Persist per-round betting snapshots for ML training."""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

from django.db import connections, transaction

from Decision.services.betting_insights import BettingInsightsError, compute_betting_insights

from ..models import RoundBettingSnapshot


def _load_option_counts_from_betting_db(*, game_round_id: int) -> Dict[str, int]:
    """
    Return {option_code: count} for the given betting-db game_round_id.

    This is a fallback when the Redis recent-bets list isn't populated.
    """
    query = """
        SELECT option_code, COUNT(*) AS cnt
        FROM client_bet
        WHERE game_round_id = %s
          AND option_code IS NOT NULL
          AND option_code <> ''
        GROUP BY option_code
        ORDER BY cnt DESC
    """
    try:
        with connections["betting"].cursor() as cursor:
            cursor.execute(query, [int(game_round_id)])
            rows = cursor.fetchall()
    except Exception:
        return {}

    counts: Dict[str, int] = {}
    for option_code, cnt in rows:
        code = str(option_code or "").strip().upper()
        if not code:
            continue
        try:
            counts[code] = int(cnt)
        except (TypeError, ValueError):
            continue
    return counts


def _option_rows_from_counts(option_counts: Dict[str, int], *, top_n: int) -> Tuple[list, list, list]:
    option_total = sum(option_counts.values()) or 0
    option_rows = [
        {
            "option_code": code,
            "count": int(count),
            "share_pct": round((int(count) / option_total) * 100, 2) if option_total else 0.0,
            "is_combo": ("AND" in code),
        }
        for code, count in option_counts.items()
    ]
    option_rows.sort(key=lambda row: row["count"], reverse=True)
    combo_rows = [row for row in option_rows if row["is_combo"]]

    selected_phase_counts: Dict[int, int] = {}

    def bump_phase(phase: int) -> None:
        selected_phase_counts[int(phase)] = int(selected_phase_counts.get(int(phase), 0)) + 1

    for code, count in option_counts.items():
        if len(code) == 2 and code[0] in {"F", "D"} and code[1].isdigit():
            bump_phase(int(code[1]))
            continue
        normalized = code.replace(" ", "")
        if normalized.startswith("F") and "ANDD" in normalized:
            float_phase_str, drown_phase_str = normalized[1:].split("ANDD", 1)
            if float_phase_str.isdigit():
                bump_phase(int(float_phase_str))
            if drown_phase_str.isdigit():
                bump_phase(int(drown_phase_str))

    selected_phase_total = sum(selected_phase_counts.values()) or 0
    selected_phase_rows = [
        {
            "phase": int(phase),
            "count": int(count),
            "share_pct": round((int(count) / selected_phase_total) * 100, 2) if selected_phase_total else 0.0,
        }
        for phase, count in selected_phase_counts.items()
    ]
    selected_phase_rows.sort(key=lambda row: row["count"], reverse=True)

    return option_rows[:top_n], combo_rows[:top_n], selected_phase_rows[:top_n]


def capture_round_snapshot(
    *,
    round_id: int,
    game_round_pk: Optional[int] = None,
    top_n: int = 10,
    recent_limit: int = 1000,
) -> RoundBettingSnapshot:
    """
    Capture live redis betting insights into the ML database.

    Should be called at round close (before Redis state is cleared) so the snapshot is per-round.
    """
    top_n = max(1, min(int(top_n), 50))
    recent_limit = max(50, min(int(recent_limit), 20000))

    try:
        insights = compute_betting_insights(top_n=top_n, recent_limit=recent_limit)
    except BettingInsightsError as exc:
        insights = {
            "total_pool": 0.0,
            "total_bets": 0,
            "top_characters": [],
            "top_phases_live": [],
            "top_options_recent": [],
            "top_combos_recent": [],
            "top_phases_selected_recent": [],
            "recent_window_size": 0,
            "source": {"error": str(exc)},
        }

    # If Redis recent bet list isn't populated, fall back to betting DB option counts.
    if not insights.get("top_options_recent"):
        option_counts = _load_option_counts_from_betting_db(game_round_id=int(round_id))
        if not option_counts and game_round_pk and int(game_round_pk) != int(round_id):
            option_counts = _load_option_counts_from_betting_db(game_round_id=int(game_round_pk))
        if option_counts:
            options, combos, phases_selected = _option_rows_from_counts(option_counts, top_n=top_n)
            insights["top_options_recent"] = options
            insights["top_combos_recent"] = combos
            insights["top_phases_selected_recent"] = phases_selected
            source = insights.get("source") or {}
            source["betting_db"] = {"client_bet_game_round_id": int(round_id)}
            insights["source"] = source

    thresholds = {
        "bonus_round": {
            "min_total_bets": int(os.getenv("BONUS_ROUND_MIN_TOTAL_BETS", "500")),
            "min_total_stake": float(os.getenv("BONUS_ROUND_MIN_TOTAL_STAKE", "5000")),
        }
    }

    with transaction.atomic():
        snapshot = RoundBettingSnapshot.objects.create(
            round_id=int(round_id),
            game_round_pk=int(game_round_pk) if game_round_pk is not None else None,
            total_pool=float(insights.get("total_pool") or 0.0),
            total_bets=int(insights.get("total_bets") or 0),
            top_characters=list(insights.get("top_characters") or []),
            top_phases_live=list(insights.get("top_phases_live") or []),
            top_options=list(insights.get("top_options_recent") or []),
            top_combos=list(insights.get("top_combos_recent") or []),
            top_phases_selected=list(insights.get("top_phases_selected_recent") or []),
            thresholds=thresholds,
            source=dict(insights.get("source") or {}),
        )
    return snapshot
