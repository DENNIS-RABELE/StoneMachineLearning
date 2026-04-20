import os
import time

import redis
from redis.exceptions import RedisError


REDIS_URL = os.getenv(
    "ROUND_TIMER_REDIS_URL",
    os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")),
)
REDIS_ROUND_TIMER_KEY = os.getenv("REDIS_ROUND_TIMER_KEY", "round:timer:state")
DEFAULT_ROUND_DURATION_SECONDS = max(1, int(os.getenv("ROUND_DURATION_SECONDS", "200")))
_redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
)


class RoundTimerStoreError(Exception):
    pass


def _to_int(value, default):
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def get_round_timer_snapshot(now_ms=None):
    """
    Read the canonical round timer state from Redis and return a computed snapshot.

    The canonical countdown source is the Decision service Celery task
    `process_round_lifecycle_task`, which updates Redis every
    ROUND_TICK_SECONDS. All clients and downstream services should sync to
    this Redis state and not derive countdown time independently.

    Returns None when the timer key does not exist.
    """
    try:
        payload = _redis_client.hgetall(REDIS_ROUND_TIMER_KEY)
    except RedisError as exc:
        raise RoundTimerStoreError(str(exc)) from exc

    if not payload:
        return None

    now_epoch_ms = _to_int(now_ms, int(time.time() * 1000))
    start_time_ms = _to_int(payload.get("startTimeMs"), now_epoch_ms)
    duration_seconds = max(1, _to_int(payload.get("durationSeconds"), DEFAULT_ROUND_DURATION_SECONDS))
    elapsed_seconds = max(0, (now_epoch_ms - start_time_ms) // 1000)
    seconds_remaining = max(0, duration_seconds - elapsed_seconds)

    return {
        "roundId": _to_int(payload.get("roundId"), 0),
        "status": payload.get("status") or "OPEN",
        "durationSeconds": int(duration_seconds),
        "secondsElapsed": int(elapsed_seconds),
        "secondsRemaining": int(seconds_remaining),
        "startTimeMs": int(start_time_ms),
        "endTimeMs": _to_int(payload.get("endTimeMs"), 0) or None,
        "serverTimeMs": int(now_epoch_ms),
        "source": "redis",
    }
