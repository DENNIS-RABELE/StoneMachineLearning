from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.utils import timezone
import os
import redis
from redis.exceptions import RedisError
from .models import Bet_decision, Character
from .round_timer import get_round_timer_snapshot, RoundTimerStoreError
from .serializers import BetSerializer, RoundStatusSerializer
from .services.decision_engine import DecisionEngine
from .models import PhaseCharacterMarket
from .services.betting_insights import BettingInsightsError, compute_betting_insights

REDIS_URL = os.getenv(
    "BETS_REDIS_URL",
    os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")),
)
REDIS_BETS_BY_CHAR_KEY = os.getenv(
    "REDIS_BETS_BY_CHAR_KEY", "round:current:bets:by_character"
)
REDIS_BETS_BY_CHAR_COUNT_KEY = os.getenv(
    "REDIS_BETS_BY_CHAR_COUNT_KEY", "round:current:bets:by_character:count"
)
REDIS_BETS_BY_CHAR_ODDS_KEY = os.getenv(
    "REDIS_BETS_BY_CHAR_ODDS_KEY", "round:current:bets:by_character:odds_sum"
)
REDIS_BETS_CHAR_NAMES_KEY = os.getenv(
    "REDIS_BETS_CHAR_NAMES_KEY", "round:current:bets:character_names"
)


class BetViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for betting decisions"""
    queryset = Bet_decision.objects.all()
    serializer_class = BetSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent bets"""
        recent_bets = Bet_decision.objects.all().order_by('-created_at')[:10]
        serializer = self.get_serializer(recent_bets, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def realtime(self, request):
        """Get realtime betting data"""
        total_bets = Bet_decision.objects.count()
        return Response({
            'total_bets': total_bets,
            'timestamp': timezone.now(),
        })


class RoundViewSet(viewsets.ViewSet):
    """ViewSet for round management"""
    
    @action(detail=False, methods=['get'])
    def current_status(self, request):
        """Get current round status"""
        characters_count = Character.objects.count()
        decisions_count = Bet_decision.objects.count()
        snapshot = None
        try:
            snapshot = get_round_timer_snapshot()
        except RoundTimerStoreError:
            snapshot = None
        
        return Response({
            'round_id': snapshot["roundId"] if snapshot else 1,
            'status': snapshot["status"] if snapshot else 'waiting',
            'time_remaining': snapshot["secondsRemaining"] if snapshot else 0,
            'duration_seconds': snapshot["durationSeconds"] if snapshot else 0,
            'total_bets': decisions_count,
            'active_characters': characters_count,
            'timestamp': timezone.now(),
        })
    
    def list(self, request):
        """List all rounds"""
        return Response({
            'message': 'Use /rounds/current_status/ for current round status',
            'available_endpoints': [
                '/rounds/current_status/ - Get current round status'
            ]
        })

    @action(detail=False, methods=["get"])
    def bonus_status(self, request):
        """
        Report whether current betting volume is high enough to trigger a bonus round.

        Uses Redis live counters from `current_bets_by_character`.
        Thresholds are configurable via env vars:
        - BONUS_ROUND_MIN_TOTAL_BETS (default: 500)
        - BONUS_ROUND_MIN_TOTAL_STAKE (default: 5000)
        """
        min_total_bets = int(os.getenv("BONUS_ROUND_MIN_TOTAL_BETS", "500"))
        min_total_stake = float(os.getenv("BONUS_ROUND_MIN_TOTAL_STAKE", "5000"))

        try:
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            totals = client.hgetall(REDIS_BETS_BY_CHAR_KEY)
            counts = client.hgetall(REDIS_BETS_BY_CHAR_COUNT_KEY)
        except RedisError as exc:
            return Response(
                {"error": "redis_unavailable", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        total_stake = 0.0
        for field, raw_value in totals.items():
            if not str(field).endswith(":TOTAL"):
                continue
            try:
                total_stake += float(raw_value)
            except (TypeError, ValueError):
                continue

        total_count = 0
        for field, raw_value in counts.items():
            if not str(field).endswith(":TOTAL:COUNT"):
                continue
            try:
                total_count += int(raw_value)
            except (TypeError, ValueError):
                continue

        eligible = bool(total_count >= min_total_bets or total_stake >= min_total_stake)
        reason = []
        if total_count >= min_total_bets:
            reason.append("total_bets")
        if total_stake >= min_total_stake:
            reason.append("total_stake")

        return Response(
            {
                "eligible": eligible,
                "reason": reason,
                "thresholds": {
                    "min_total_bets": min_total_bets,
                    "min_total_stake": min_total_stake,
                },
                "current": {
                    "total_bets": total_count,
                    "total_stake": round(total_stake, 2),
                },
                "timestamp": timezone.now(),
            }
        )

    @action(detail=False, methods=["get"])
    def betting_insights(self, request):
        """
        Summarize current betting popularity and odds signals.

        Data sources:
        - Per-character/phase stake + count + odds_sum from the existing Redis hashes.
        - Most-bet option combinations from the Redis recent-bets list (optionCode).
        """
        top_n_raw = request.query_params.get("top") or "10"
        recent_limit_raw = request.query_params.get("recent_limit") or "1000"
        try:
            top_n = max(1, min(int(top_n_raw), 50))
        except ValueError:
            top_n = 10
        try:
            recent_limit = max(50, min(int(recent_limit_raw), 20000))
        except ValueError:
            recent_limit = 1000

        try:
            insights = compute_betting_insights(top_n=top_n, recent_limit=recent_limit)
        except BettingInsightsError as exc:
            return Response(
                {"error": "redis_unavailable", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        round_id = None
        try:
            snapshot = get_round_timer_snapshot()
            if snapshot:
                round_id = snapshot.get("roundId")
        except RoundTimerStoreError:
            round_id = None

        return Response(
            {
                "round_id": round_id,
                "total_pool": insights["total_pool"],
                "total_bets": insights["total_bets"],
                "top_characters": insights["top_characters"],
                "top_phases_live": insights["top_phases_live"],
                "top_options_recent": insights["top_options_recent"],
                "top_combos_recent": insights["top_combos_recent"],
                "top_phases_selected_recent": insights["top_phases_selected_recent"],
                "recent_window_size": insights["recent_window_size"],
                "timestamp": timezone.now(),
            }
        )


# Legacy views for backward compatibility
@api_view(['GET'])
def realtime_bets(request):
    """Legacy endpoint: Get realtime betting data"""
    total_bets = Bet_decision.objects.count()
    return Response({
        'total_bets': total_bets,
        'timestamp': timezone.now(),
    })


@api_view(['GET'])
def phase_bet_summary(request):
    """Legacy endpoint: Get phase summary of bets"""
    decisions = Bet_decision.objects.all()
    return Response({
        'total_decisions': decisions.count(),
        'results': {
            decision.round_result: Bet_decision.objects.filter(round_result=decision.round_result).count()
            for decision in decisions.distinct('round_result')
        },
        'timestamp': timezone.now(),
    })


@api_view(['GET'])
def round_timer(request):
    """Legacy endpoint: Get round timer info"""
    try:
        snapshot = get_round_timer_snapshot()
    except RoundTimerStoreError as exc:
        return Response(
            {
                "error": "round_timer_unavailable",
                "detail": str(exc),
                "timestamp": timezone.now(),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not snapshot:
        return Response(
            {
                "round_id": 1,
                "time_remaining": 0,
                "status": "waiting",
                "timestamp": timezone.now(),
            }
        )

    return Response(
        {
            "round_id": snapshot["roundId"],
            "time_remaining": snapshot["secondsRemaining"],
            "status": snapshot["status"],
            "duration_seconds": snapshot["durationSeconds"],
            "server_time_ms": snapshot["serverTimeMs"],
            "start_time_ms": snapshot["startTimeMs"],
            "end_time_ms": snapshot["endTimeMs"] or (
                snapshot["startTimeMs"] + (snapshot["durationSeconds"] * 1000)
            ),
            "timestamp": timezone.now(),
        }
    )


@api_view(['GET'])
def current_bets_by_character(request):
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        totals = client.hgetall(REDIS_BETS_BY_CHAR_KEY)
        counts = client.hgetall(REDIS_BETS_BY_CHAR_COUNT_KEY)
        odds_totals = client.hgetall(REDIS_BETS_BY_CHAR_ODDS_KEY)
        names = client.hgetall(REDIS_BETS_CHAR_NAMES_KEY)
    except RedisError as exc:
        return Response(
            {"error": "redis_unavailable", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    characters = {}
    for field, raw_value in totals.items():
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if field.endswith(":TOTAL"):
            try:
                char_id = int(field.split(":")[0].lstrip("C"))
            except ValueError:
                continue
            entry = characters.setdefault(
                char_id,
                {
                    "character_id": char_id,
                    "character_name": names.get(str(char_id)),
                    "total_stake": 0,
                    "total_count": 0,
                    "float": {},
                    "drown": {},
                },
            )
            entry["total_stake"] += value
            continue

        parts = field.split(":")
        if len(parts) != 3:
            continue
        char_part, kind, phase_raw = parts
        try:
            char_id = int(char_part.lstrip("C"))
            phase = int(phase_raw)
        except ValueError:
            continue
        kind_key = "float" if kind.upper() == "FLOAT" else "drown"
        entry = characters.setdefault(
            char_id,
            {
                "character_id": char_id,
                "character_name": names.get(str(char_id)),
                "total_stake": 0,
                "total_count": 0,
                "float": {},
                "drown": {},
            },
        )
        phase_key = str(phase)
        phase_entry = entry[kind_key].setdefault(
            phase_key,
            {"stake": 0, "count": 0, "total_odds": 0},
        )
        phase_entry["stake"] += value

    for field, raw_value in counts.items():
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            continue
        if field.endswith(":TOTAL:COUNT"):
            try:
                char_id = int(field.split(":")[0].lstrip("C"))
            except ValueError:
                continue
            entry = characters.setdefault(
                char_id,
                {
                    "character_id": char_id,
                    "character_name": names.get(str(char_id)),
                    "total_stake": 0,
                    "total_count": 0,
                    "float": {},
                    "drown": {},
                },
            )
            entry["total_count"] += value
            continue

        parts = field.split(":")
        if len(parts) != 4:
            continue
        char_part, kind, phase_raw, _count = parts
        try:
            char_id = int(char_part.lstrip("C"))
            phase = int(phase_raw)
        except ValueError:
            continue
        kind_key = "float" if kind.upper() == "FLOAT" else "drown"
        entry = characters.setdefault(
            char_id,
            {
                "character_id": char_id,
                "character_name": names.get(str(char_id)),
                "total_stake": 0,
                "total_count": 0,
                "float": {},
                "drown": {},
            },
        )
        phase_key = str(phase)
        phase_entry = entry[kind_key].setdefault(
            phase_key,
            {"stake": 0, "count": 0, "total_odds": 0},
        )
        phase_entry["count"] += value

    for field, raw_value in odds_totals.items():
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if field.endswith(":TOTAL:ODDS"):
            try:
                char_id = int(field.split(":")[0].lstrip("C"))
            except ValueError:
                continue
            entry = characters.setdefault(
                char_id,
                {
                    "character_id": char_id,
                    "character_name": names.get(str(char_id)),
                    "total_stake": 0,
                    "total_count": 0,
                    "float": {},
                    "drown": {},
                },
            )
            entry["total_odds_sum"] = entry.get("total_odds_sum", 0) + value
            continue

        parts = field.split(":")
        if len(parts) != 4:
            continue
        char_part, kind, phase_raw, _odds = parts
        try:
            char_id = int(char_part.lstrip("C"))
            phase = int(phase_raw)
        except ValueError:
            continue
        kind_key = "float" if kind.upper() == "FLOAT" else "drown"
        entry = characters.setdefault(
            char_id,
            {
                "character_id": char_id,
                "character_name": names.get(str(char_id)),
                "total_stake": 0,
                "total_count": 0,
                "float": {},
                "drown": {},
            },
        )
        phase_key = str(phase)
        phase_entry = entry[kind_key].setdefault(
            phase_key,
            {"stake": 0, "count": 0, "total_odds": 0},
        )
        phase_entry["total_odds"] += value

    payload = list(characters.values())
    total_pool = sum(item.get("total_stake", 0) for item in payload)
    for entry in payload:
        entry["percentage_of_pool"] = (
            round((entry.get("total_stake", 0) / total_pool) * 100, 4)
            if total_pool
            else 0
        )
        for kind_key in ("float", "drown"):
            for phase_key, phase_entry in entry[kind_key].items():
                phase_entry["percentage_of_pool"] = (
                    round((phase_entry.get("stake", 0) / total_pool) * 100, 4)
                    if total_pool
                    else 0
                )

    payload.sort(key=lambda item: item.get("total_stake", 0), reverse=True)

    round_id = None
    try:
        snapshot = get_round_timer_snapshot()
        if snapshot:
            round_id = snapshot.get("roundId")
    except RoundTimerStoreError:
        round_id = None

    return Response(
        {
            "round_id": round_id,
            "total_pool": total_pool,
            "percentage_distribution": True,
            "characters": payload,
            "timestamp": timezone.now(),
        }
    )

@api_view(['GET'])
def latest_characters(request):
    limit = request.query_params.get("limit")
    ids = request.query_params.get("ids")

    try:
        limit_value = max(1, int(limit)) if limit is not None else 5
    except (TypeError, ValueError):
        limit_value = 5

    queryset = Character.objects.all()
    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if str(x).strip()]
        except ValueError:
            return Response(
                {"error": "invalid_ids", "detail": "ids must be comma-separated integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(id__in=id_list)

    characters = list(queryset.order_by("-created_at", "-id")[:limit_value])

    return Response(
        {
            "count": len(characters),
            "results": [
                {
                    "id": char.id,
                    "name": char.name,
                    "stamina": char.stamina,
                    "control": char.control,
                    "power": char.power,
                    "created_at": char.created_at,
                }
                for char in characters
            ],
        }
    )


@api_view(['GET'])
def market_summary(request, market_id: int):
    engine = DecisionEngine()
    try:
        summary = engine.market_summary(market_id)
    except PhaseCharacterMarket.DoesNotExist:
        return Response(
            {"error": "market_not_found", "detail": "Market not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(summary)
