import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import redis
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import Bet_decision, GameRound, RoundStatus
from .services.redis_market_store import RedisMarketStoreError, clear_round_state
from .services.round_outcome_service import (
    prepare_open_decision_round_for_client_round,
    resolve_current_decision_round_for_client_round,
)

try:
    from Gameplay.state import get_global_gameplay_state, start_gameplay, stop_gameplay
except ImportError:
    get_global_gameplay_state = lambda *args, **kwargs: None
    start_gameplay = lambda *args, **kwargs: None
    stop_gameplay = lambda *args, **kwargs: None


REDIS_URL = os.getenv(
    "ROUND_TIMER_REDIS_URL",
    os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")),
)
REDIS_ROUND_TIMER_KEY = os.getenv("REDIS_ROUND_TIMER_KEY", "round:timer:state")
ROUND_DURATION_SECONDS = max(1, int(os.getenv("ROUND_DURATION_SECONDS", "200")))
GAMEPLAY_START_DELAY_SECONDS = max(0, int(os.getenv("GAMEPLAY_START_DELAY_SECONDS", "40")))
STATS_WINDOW_SECONDS = max(0, int(os.getenv("STATS_WINDOW_SECONDS", "120")))
GAMEPLAY_ACTIVE_SECONDS = max(
    0,
    ROUND_DURATION_SECONDS - GAMEPLAY_START_DELAY_SECONDS - STATS_WINDOW_SECONDS,
)
_gateway_hostport = os.getenv("GATEWAY_HOSTPORT", "").strip()
GATEWAY_URL = os.getenv(
    "GATEWAY_URL",
    f"http://{_gateway_hostport}" if _gateway_hostport else "http://127.0.0.1:9006",
)
BETDATA_SYNC_PATH = os.getenv(
    "BETDATA_SYNC_PATH",
    "/api/bettor/betdata/api/bets/sync-status/",
)


def _redis_client():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _as_epoch_ms(value):
    if value is None:
        return int(time.time() * 1000)
    return int(value.timestamp() * 1000)


def _upsert_round_timer_state(round_obj):
    client = _redis_client()
    start_time_ms = _as_epoch_ms(round_obj.start_time)
    end_time_ms = _as_epoch_ms(round_obj.end_time) if round_obj.end_time else ""
    now_ms = int(time.time() * 1000)
    elapsed_seconds = max(0, (now_ms - start_time_ms) // 1000)
    seconds_remaining = max(0, ROUND_DURATION_SECONDS - int(elapsed_seconds))

    print(
        f"[Decision] Upserting timer: round {round_obj.round_id}, "
        f"elapsed {elapsed_seconds}s, remaining {seconds_remaining}s"
    )

    client.hset(
        REDIS_ROUND_TIMER_KEY,
        mapping={
            "roundId": str(int(round_obj.round_id)),
            "status": str(round_obj.status),
            "startTimeMs": str(start_time_ms),
            "endTimeMs": str(end_time_ms),
            "durationSeconds": str(ROUND_DURATION_SECONDS),
            "secondsRemaining": str(int(seconds_remaining)),
            "serverTimeMs": str(int(now_ms)),
        },
    )


def _seconds_elapsed_from_start(start_time):
    delta = timezone.now() - start_time
    return max(0, int(delta.total_seconds()))


def _gameplay_should_be_running(elapsed: int, remaining: int) -> bool:
    if ROUND_DURATION_SECONDS <= 0:
        return False
    # Loop rule:
    # - start when countdown reaches 00:30
    # - keep running through the round rollover
    # - stop when the next round countdown reaches 02:00
    return remaining <= GAMEPLAY_START_DELAY_SECONDS or remaining > STATS_WINDOW_SECONDS


def _sync_global_gameplay_state(*, elapsed: int, remaining: int) -> None:
    desired_running = _gameplay_should_be_running(elapsed=elapsed, remaining=remaining)
    state = get_global_gameplay_state()
    current_status = str(getattr(state, "status", "") or "").upper()
    current_max_ticks = int(getattr(state, "max_ticks", 0) or 0)

    if desired_running:
        if current_status != "RUNNING" or current_max_ticks != GAMEPLAY_ACTIVE_SECONDS:
            start_gameplay(max_ticks=GAMEPLAY_ACTIVE_SECONDS, reset_tick=True)
        return

    if current_status == "RUNNING":
        stop_gameplay()


def _notify_betdata_sync(round_id, status_value):
    base = str(GATEWAY_URL).rstrip("/")
    path = str(BETDATA_SYNC_PATH or "/api/bettor/betdata/api/bets/sync-status/")
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base}{path}"
    payload = json.dumps({"round_id": int(round_id), "status": str(status_value)}).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            response.read()
    except (HTTPError, URLError) as exc:
        print(f"[Decision] Betdata sync failed: {exc}")


def ensure_open_round():
    with transaction.atomic():
        open_round = (
            GameRound.objects.select_for_update()
            .filter(status=RoundStatus.OPEN)
            .order_by("-round_id")
            .first()
        )
        if open_round:
            return open_round

        max_round_id = GameRound.objects.aggregate(max_round_id=Max("round_id"))["max_round_id"] or 0
        open_round = GameRound.objects.create(
            round_id=max_round_id + 1,
            start_time=timezone.now(),
            status=RoundStatus.OPEN,
        )
        prepare_open_decision_round_for_client_round(client_round_id=open_round.id)
        return open_round


def progress_round_if_due():
    print("[Decision] progress_round_if_due called")
    open_round = ensure_open_round()
    elapsed = _seconds_elapsed_from_start(open_round.start_time)
    remaining = ROUND_DURATION_SECONDS - elapsed
    _sync_global_gameplay_state(elapsed=elapsed, remaining=remaining)

    if elapsed < ROUND_DURATION_SECONDS:
        _upsert_round_timer_state(open_round)
        print(f"[Decision] Round {open_round.round_id}: elapsed {elapsed}s, remaining {remaining}s")
        return {
            "action": "noop",
            "round_id": int(open_round.round_id),
            "elapsed_seconds": elapsed,
        }

    with transaction.atomic():
        locked_round = (
            GameRound.objects.select_for_update()
            .filter(id=open_round.id, status=RoundStatus.OPEN)
            .first()
        )
        if not locked_round:
            return {"action": "race_lost"}

        locked_round.status = RoundStatus.CLOSED
        locked_round.end_time = timezone.now()
        locked_round.save(update_fields=["status", "end_time"])
        _notify_betdata_sync(locked_round.round_id, locked_round.status)

        # Capture round-level popularity/odds snapshot before Redis state is cleared.
        try:
            from ml.services.round_betting_snapshot import capture_round_snapshot

            capture_round_snapshot(
                round_id=int(locked_round.round_id),
                game_round_pk=int(locked_round.id),
                top_n=max(5, int(os.getenv("ROUND_SNAPSHOT_TOP_N", "15"))),
                recent_limit=max(200, int(os.getenv("ROUND_SNAPSHOT_RECENT_LIMIT", "5000"))),
            )
        except Exception as exc:
            print(f"[Decision] Round snapshot capture failed: {exc}")

        resolution = resolve_current_decision_round_for_client_round(client_round_id=locked_round.id)
        try:
            clear_round_state()
        except RedisMarketStoreError:
            pass

        next_round = GameRound.objects.create(
            round_id=locked_round.round_id + 1,
            start_time=timezone.now(),
            status=RoundStatus.OPEN,
        )
        prepare_open_decision_round_for_client_round(client_round_id=next_round.id)
        Bet_decision.objects.create(round_result=resolution.get("summary_result", "RESOLVED")[:16])

    _sync_global_gameplay_state(elapsed=0, remaining=ROUND_DURATION_SECONDS)
    _upsert_round_timer_state(next_round)

    return {
        "action": "closed_and_opened",
        "closed_round_id": int(locked_round.round_id),
        "next_round_id": int(next_round.round_id),
        "decision_round_id": resolution.get("decision_round_id"),
        "next_decision_round_id": resolution.get("next_decision_round_id"),
        "generated_outcomes": resolution.get("generated_outcomes", 0),
        "summary_result": resolution.get("summary_result", "RESOLVED"),
    }
