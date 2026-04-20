import json
import os

import redis
from redis.exceptions import RedisError


REDIS_URL = os.getenv("BETS_REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
REDIS_BETS_KEY = os.getenv("REDIS_BETS_KEY", "round:current:bets")


class RedisBetStoreError(Exception):
    pass


def _decode_payload(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"value": value}

    return value


def get_latest_bets(limit=None):
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        key_type = client.type(REDIS_BETS_KEY)

        if key_type == "none":
            return []

        if key_type == "stream":
            if limit is None:
                items = client.xrevrange(REDIS_BETS_KEY)
            else:
                items = client.xrevrange(REDIS_BETS_KEY, count=limit)
            items.reverse()
            return [{"redis_id": item_id, **fields} for item_id, fields in items]

        if key_type == "hash":
            items = client.hgetall(REDIS_BETS_KEY)
            parsed = []
            for selection, stake in items.items():
                try:
                    numeric_stake = float(stake)
                except (TypeError, ValueError):
                    numeric_stake = stake
                parsed.append({"selection": selection, "stake": numeric_stake})

            # Return highest stakes first for easier realtime display.
            parsed.sort(
                key=lambda row: row["stake"] if isinstance(row["stake"], (int, float)) else -1,
                reverse=True,
            )
            return parsed if limit is None else parsed[:limit]

        if key_type == "list":
            end_index = -1 if limit is None else max(0, limit - 1)
            items = client.lrange(REDIS_BETS_KEY, 0, end_index)
            return [_decode_payload(item) for item in items]

        if key_type == "zset":
            end_index = -1 if limit is None else max(0, limit - 1)
            items = client.zrevrange(REDIS_BETS_KEY, 0, end_index, withscores=True)
            return [{"payload": _decode_payload(payload), "score": score} for payload, score in items]

        if key_type == "string":
            value = client.get(REDIS_BETS_KEY)
            if value is None:
                return []
            decoded = _decode_payload(value)
            if isinstance(decoded, list):
                return decoded if limit is None else decoded[:limit]
            return [decoded]

        raise RedisBetStoreError(f"Unsupported Redis key type '{key_type}' for key '{REDIS_BETS_KEY}'.")
    except RedisError as exc:
        raise RedisBetStoreError(str(exc)) from exc
