import json
import os
from functools import lru_cache
from decimal import Decimal
from typing import Dict, Iterable, Optional

import redis
from redis.exceptions import RedisError


class RedisMarketStoreError(Exception):
    pass


REDIS_URL = os.getenv("BETS_REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
if REDIS_URL.startswith("redis://localhost"):
    REDIS_URL = REDIS_URL.replace("redis://localhost", "redis://127.0.0.1", 1)
REDIS_SOCKET_CONNECT_TIMEOUT = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "1"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "1"))
REDIS_HEALTH_CHECK_INTERVAL = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))
RECENT_BETS_STREAM = os.getenv("REDIS_BETS_STREAM_KEY", "bets:stream")
SHARED_STAKE_TOTALS_KEY = os.getenv(
    "REDIS_SHARED_STAKE_TOTALS_KEY",
    "round:current:stakes:by_character_phase_outcome",
)
ROUND_CURRENT_BETS_KEY = os.getenv("REDIS_BETS_KEY", "round:current:bets")


def _market_totals_key(market_id: int) -> str:
    return f"market:{market_id}:totals"


def _market_meta_key(market_id: int) -> str:
    return f"market:{market_id}:meta"


def _to_decimal(value: Optional[str], default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


@lru_cache(maxsize=1)
def get_client():
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        health_check_interval=REDIS_HEALTH_CHECK_INTERVAL,
    )


def _shared_stake_field(character_id: int, phase_number: int, outcome_code: str) -> str:
    return f"C{int(character_id)}:P{int(phase_number)}:{str(outcome_code).upper()}"


def get_market_totals(market_id: int) -> Dict[str, Decimal]:
    try:
        raw = get_client().hgetall(_market_totals_key(market_id))
        return {
            "FLOAT": _to_decimal(raw.get("FLOAT")),
            "DROWN": _to_decimal(raw.get("DROWN")),
        }
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def get_shared_character_phase_totals(character_id: int, phase_number: int) -> Dict[str, Decimal]:
    float_field = _shared_stake_field(character_id, phase_number, "FLOAT")
    drown_field = _shared_stake_field(character_id, phase_number, "DROWN")
    try:
        client = get_client()
        raw = client.hmget(SHARED_STAKE_TOTALS_KEY, [float_field, drown_field])
        return {
            "FLOAT": _to_decimal(raw[0] if raw else None),
            "DROWN": _to_decimal(raw[1] if raw else None),
        }
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def set_market_totals(market_id: int, totals: Dict[str, Decimal]) -> None:
    try:
        get_client().hset(
            _market_totals_key(market_id),
            mapping={
                "FLOAT": str(totals.get("FLOAT", Decimal("0"))),
                "DROWN": str(totals.get("DROWN", Decimal("0"))),
            },
        )
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def clear_round_state() -> None:
    try:
        get_client().delete(SHARED_STAKE_TOTALS_KEY, ROUND_CURRENT_BETS_KEY)
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def increment_market_stake(market_id: int, outcome_code: str, stake: Decimal) -> Dict[str, Decimal]:
    try:
        client = get_client()
        client.hincrbyfloat(_market_totals_key(market_id), outcome_code, float(stake))
        return get_market_totals(market_id)
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def set_market_snapshot(
    market_id: int,
    odds: Dict[str, Decimal],
    recommended_outcome: str,
    stake_difference: Decimal,
) -> None:
    try:
        get_client().hset(
            _market_meta_key(market_id),
            mapping={
                "odds_FLOAT": str(odds.get("FLOAT", Decimal("1.00"))),
                "odds_DROWN": str(odds.get("DROWN", Decimal("1.00"))),
                "recommended_outcome": recommended_outcome,
                "stake_difference": str(stake_difference),
            },
        )
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def append_recent_bet(payload: Dict[str, object]) -> None:
    try:
        get_client().xadd(
            RECENT_BETS_STREAM,
            {"payload": json.dumps(payload, default=str)},
            maxlen=10000,
            approximate=True,
        )
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc


def get_recent_bets(limit: Optional[int] = 100) -> Iterable[Dict[str, object]]:
    try:
        client = get_client()
        items = client.xrevrange(RECENT_BETS_STREAM) if limit is None else client.xrevrange(RECENT_BETS_STREAM, count=max(1, limit))
        rows = []
        for redis_id, fields in reversed(items):
            payload = fields.get("payload")
            if payload:
                try:
                    decoded = json.loads(payload)
                except json.JSONDecodeError:
                    decoded = {"raw": payload}
            else:
                decoded = {}
            rows.append({"redis_id": redis_id, **decoded})
        return rows
    except RedisError as exc:
        raise RedisMarketStoreError(str(exc)) from exc
