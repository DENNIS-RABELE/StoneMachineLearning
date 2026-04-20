"""Helpers to summarize live betting popularity and odds signals from Redis."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

import redis
from redis.exceptions import RedisError


class BettingInsightsError(Exception):
    pass


def compute_betting_insights(*, top_n: int = 10, recent_limit: int = 1000) -> Dict[str, object]:
    """
    Return a dict with popularity + odds summaries for the active round.

    Uses the same Redis keys as Decision/views.py current_bets_by_character.
    """
    top_n = max(1, min(int(top_n), 50))
    recent_limit = max(50, min(int(recent_limit), 20000))

    redis_url = os.getenv(
        "BETS_REDIS_URL",
        os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")),
    )
    bets_by_char_key = os.getenv("REDIS_BETS_BY_CHAR_KEY", "round:current:bets:by_character")
    bets_by_char_count_key = os.getenv(
        "REDIS_BETS_BY_CHAR_COUNT_KEY",
        "round:current:bets:by_character:count",
    )
    bets_by_char_odds_key = os.getenv(
        "REDIS_BETS_BY_CHAR_ODDS_KEY",
        "round:current:bets:by_character:odds_sum",
    )
    bets_char_names_key = os.getenv(
        "REDIS_BETS_CHAR_NAMES_KEY",
        "round:current:bets:character_names",
    )
    recent_bets_key = os.getenv("REDIS_RECENT_BETS_KEY", "round:recent:bets")

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        totals = client.hgetall(bets_by_char_key)
        counts = client.hgetall(bets_by_char_count_key)
        odds_totals = client.hgetall(bets_by_char_odds_key)
        names = client.hgetall(bets_char_names_key)
        recent_raw = client.lrange(recent_bets_key, 0, max(0, recent_limit - 1))
    except RedisError as exc:
        raise BettingInsightsError(str(exc)) from exc

    characters: Dict[int, Dict[str, object]] = {}
    total_pool = 0.0
    total_bets = 0

    for field, raw_value in totals.items():
        if not str(field).endswith(":TOTAL"):
            continue
        try:
            char_id = int(str(field).split(":")[0].lstrip("C"))
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        entry = characters.setdefault(
            char_id,
            {
                "character_id": char_id,
                "character_name": names.get(str(char_id)),
                "total_stake": 0.0,
                "total_count": 0,
            },
        )
        entry["total_stake"] = float(entry.get("total_stake") or 0.0) + value
        total_pool += value

    for field, raw_value in counts.items():
        if not str(field).endswith(":TOTAL:COUNT"):
            continue
        try:
            char_id = int(str(field).split(":")[0].lstrip("C"))
            value = int(raw_value)
        except (TypeError, ValueError):
            continue
        entry = characters.setdefault(
            char_id,
            {
                "character_id": char_id,
                "character_name": names.get(str(char_id)),
                "total_stake": 0.0,
                "total_count": 0,
            },
        )
        entry["total_count"] = int(entry.get("total_count") or 0) + value
        total_bets += value

    phase_counts: Dict[int, Dict[str, float]] = {}
    phase_stakes: Dict[int, Dict[str, float]] = {}
    phase_odds_sums: Dict[int, Dict[str, float]] = {}

    def bump_phase(target: Dict[int, Dict[str, float]], phase: int, kind: str, value: float) -> None:
        row = target.setdefault(int(phase), {"FLOAT": 0.0, "DROWN": 0.0})
        row["FLOAT" if kind.upper() == "FLOAT" else "DROWN"] += float(value)

    for field, raw_value in totals.items():
        parts = str(field).split(":")
        if len(parts) != 3:
            continue
        _char_part, kind, phase_raw = parts
        if phase_raw.upper() == "TOTAL":
            continue
        try:
            phase = int(phase_raw)
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        bump_phase(phase_stakes, phase, kind, value)

    for field, raw_value in counts.items():
        parts = str(field).split(":")
        if len(parts) != 4:
            continue
        _char_part, kind, phase_raw, _count = parts
        try:
            phase = int(phase_raw)
            value = float(int(raw_value))
        except (TypeError, ValueError):
            continue
        bump_phase(phase_counts, phase, kind, value)

    for field, raw_value in odds_totals.items():
        parts = str(field).split(":")
        if len(parts) != 4:
            continue
        _char_part, kind, phase_raw, _odds = parts
        if phase_raw.upper() == "TOTAL":
            continue
        try:
            phase = int(phase_raw)
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        bump_phase(phase_odds_sums, phase, kind, value)

    phase_rows: List[Dict[str, object]] = []
    for phase in sorted(set(phase_counts) | set(phase_stakes) | set(phase_odds_sums)):
        counts_row = phase_counts.get(phase, {"FLOAT": 0.0, "DROWN": 0.0})
        stakes_row = phase_stakes.get(phase, {"FLOAT": 0.0, "DROWN": 0.0})
        odds_row = phase_odds_sums.get(phase, {"FLOAT": 0.0, "DROWN": 0.0})
        float_count = int(counts_row.get("FLOAT", 0) or 0)
        drown_count = int(counts_row.get("DROWN", 0) or 0)
        phase_rows.append(
            {
                "phase": int(phase),
                "total_count": int(float_count + drown_count),
                "total_stake": round(float(stakes_row.get("FLOAT", 0.0) + stakes_row.get("DROWN", 0.0)), 2),
                "float": {
                    "count": float_count,
                    "stake": round(float(stakes_row.get("FLOAT", 0.0)), 2),
                    "avg_odds": round(float(odds_row.get("FLOAT", 0.0)) / float_count, 4) if float_count else None,
                },
                "drown": {
                    "count": drown_count,
                    "stake": round(float(stakes_row.get("DROWN", 0.0)), 2),
                    "avg_odds": round(float(odds_row.get("DROWN", 0.0)) / drown_count, 4) if drown_count else None,
                },
            }
        )
    phase_rows.sort(key=lambda row: (row["total_count"], row["total_stake"]), reverse=True)

    option_counts: Dict[str, int] = {}
    selected_phase_counts: Dict[int, int] = {}

    def bump_selected_phase(phase: int) -> None:
        selected_phase_counts[int(phase)] = int(selected_phase_counts.get(int(phase), 0)) + 1

    for raw in recent_raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        option_code = str(
            parsed.get("optionCode")
            or parsed.get("option_code")
            or parsed.get("selection")
            or ""
        ).strip().upper()
        if not option_code:
            continue
        option_counts[option_code] = int(option_counts.get(option_code, 0)) + 1

        if len(option_code) == 2 and option_code[0] in {"F", "D"} and option_code[1].isdigit():
            bump_selected_phase(int(option_code[1]))
            continue
        normalized = option_code.replace(" ", "")
        if normalized.startswith("F") and "ANDD" in normalized:
            float_phase_str, drown_phase_str = normalized[1:].split("ANDD", 1)
            if float_phase_str.isdigit():
                bump_selected_phase(int(float_phase_str))
            if drown_phase_str.isdigit():
                bump_selected_phase(int(drown_phase_str))

    option_total = sum(option_counts.values()) or 0
    option_rows = [
        {
            "option_code": code,
            "count": count,
            "share_pct": round((count / option_total) * 100, 2) if option_total else 0.0,
            "is_combo": ("AND" in code),
        }
        for code, count in option_counts.items()
    ]
    option_rows.sort(key=lambda row: row["count"], reverse=True)
    combo_rows = [row for row in option_rows if row["is_combo"]]

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

    character_rows = list(characters.values())
    for row in character_rows:
        row["pool_share_pct"] = round((float(row.get("total_stake", 0.0)) / total_pool) * 100, 2) if total_pool else 0.0
    character_rows.sort(key=lambda row: (row.get("total_stake", 0.0), row.get("total_count", 0)), reverse=True)

    return {
        "total_pool": round(total_pool, 2),
        "total_bets": int(total_bets),
        "top_characters": character_rows[:top_n],
        "top_phases_live": phase_rows[:top_n],
        "top_options_recent": option_rows[:top_n],
        "top_combos_recent": combo_rows[:top_n],
        "top_phases_selected_recent": selected_phase_rows[:top_n],
        "recent_window_size": len(recent_raw),
        "source": {
            "redis": {
                "bets_by_char_key": bets_by_char_key,
                "bets_by_char_count_key": bets_by_char_count_key,
                "bets_by_char_odds_key": bets_by_char_odds_key,
                "recent_bets_key": recent_bets_key,
            }
        },
    }

