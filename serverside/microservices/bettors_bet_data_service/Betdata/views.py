import json
import logging
import os
import functools
import atexit
import httpx
from django.db import connections
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Works both as a standalone service (uses `default`) and when embedded in
# bettor_service (uses `betdata` db alias).
_BETDATA_DB_ALIAS = "betdata" if "betdata" in connections.databases else "default"

# Persistent HTTP client with connection pooling (reuses TCP connections)
_http_client = httpx.Client(timeout=5.0, follow_redirects=True, limits=httpx.Limits(max_keepalive_connections=20))
atexit.register(_http_client.close)

@functools.lru_cache(maxsize=1)
def _resolve_bet_round_column():
    """
    Cache the column name lookup. Schema changes require deployments anyway,
    so caching avoids repeated expensive information_schema queries.
    """
    with connections[_BETDATA_DB_ALIAS].cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
            AND table_name = 'client_bet'
        """)
        columns = {row[0].lower(): row[0] for row in cursor.fetchall()}

        for candidate in ("game_round_id", "game_round"):
            if candidate in columns:
                return columns[candidate]

        for name, actual in columns.items():
            if "game_round" in name or name.endswith("round"):
                return actual

        raise RuntimeError("client_bet is missing game round column")

def _fetch_round_timer_snapshot():
    gateway_hostport = os.getenv("GATEWAY_HOSTPORT", "").strip()
    gateway_url = os.getenv(
        "GATEWAY_URL",
        f"http://{gateway_hostport}" if gateway_hostport else "http://127.0.0.1:9006",
    ).rstrip("/")
    timer_path = os.getenv("DECISION_ROUND_TIMER_PATH", "/api/decision/api/round/timer/")
    fallback_path = os.getenv("DECISION_ROUND_TIMER_FALLBACK", "/api/decision/api/api/round/timer/")

    for path in (timer_path, fallback_path):
        if not path:
            continue
        if not path.startswith("/"):
            path = f"/{path}"

        url = f"{gateway_url}{path}"
        if "format=" not in url:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}format=json"

        try:
            # Reuses persistent connection pool
            resp = _http_client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                continue
            logger.error(f"HTTP error fetching round timer: {e}")
            raise
        except httpx.RequestError as e:
            logger.warning(f"Network error fetching round timer from {url}: {e}")
            continue

    raise RuntimeError("Decision round timer not found after trying all endpoints")

def _sync_bet_status(round_id_override=None, status_override=None):
    if round_id_override is None:
        snapshot = _fetch_round_timer_snapshot()
        round_id = int(snapshot.get("round_id") or 0)
        status_value = str(snapshot.get("status") or "").upper()
    else:
        round_id = int(round_id_override or 0)
        status_value = str(status_override or "").upper()

    if round_id <= 0:
        raise RuntimeError("Invalid round_id from decision service")

    comparison = "<=" if status_value == "CLOSED" else "<"
    round_column = _resolve_bet_round_column()

    with connections[_BETDATA_DB_ALIAS].cursor() as cursor:
        # 1. Update round state
        cursor.execute(
            """UPDATE client_round_state
               SET current_round_id = %s,
                   current_round_status = %s,
                   updated_at = NOW()
               WHERE id = 1""",
            [round_id, status_value or "OPEN"]
        )

        # 2. Close matching bets
        query = f"""
            UPDATE client_bet
            SET status = 'CLOSED'
            WHERE status = 'OPEN'
              AND {round_column} {comparison} %s
        """
        cursor.execute(query, [round_id])
        updated = cursor.rowcount

    return {
        "round_id": round_id,
        "round_status": status_value or "UNKNOWN",
        "updated_rows": updated,
    }

@api_view(["POST", "GET"])
def sync_bet_status(request):
    try:
        payload = {}
        if request.method == "POST":
            try:
                payload = request.data or {}
            except Exception:
                payload = {}

        round_id = payload.get("round_id") if request.method == "POST" else None
        status_value = payload.get("status") if request.method == "POST" else None

        result = _sync_bet_status(round_id_override=round_id, status_override=status_value)
        return Response({
            "status": "ok",
            "detail": result,
            "timestamp": timezone.now(),
        })

    except RuntimeError as e:
        logger.warning(f"Sync bet status failed (invalid input): {e}")
        return Response({
            "status": "error",
            "error": "invalid_input",
            "detail": str(e),
            "timestamp": timezone.now(),
        }, status=status.HTTP_400_BAD_REQUEST)

    except httpx.HTTPStatusError as e:
        logger.error(f"Gateway/Decision service error: {e}")
        return Response({
            "status": "error",
            "error": "gateway_unavailable",
            "detail": str(e),
            "timestamp": timezone.now(),
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as e:
        logger.exception("Unexpected error during bet status sync")
        return Response({
            "status": "error",
            "error": "sync_failed",
            "detail": str(e),
            "timestamp": timezone.now(),
        }, status=status.HTTP_400_BAD_REQUEST)
