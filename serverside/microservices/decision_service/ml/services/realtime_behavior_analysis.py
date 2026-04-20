"""Realtime bettor behavior analysis from Redis-backed live bet data."""
import json
import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import redis
from redis.exceptions import RedisError
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


logger = logging.getLogger(__name__)


@dataclass
class BettorFeatureRow:
    """In-memory feature row for realtime clustering."""

    bettor_id: str
    total_bets: int
    total_stake: float
    average_stake: float
    stake_stddev: float
    option_diversity: float
    float_ratio: float
    double_ratio: float
    feature_vector: List[float]


class RealtimeBettingAnalysisError(Exception):
    """Raised when realtime betting data cannot be analyzed."""


class RealtimeBettingAnalyzer:
    """Analyze live bettor behavior and current character popularity."""

    RECENT_BETS_KEY = os.getenv("REDIS_RECENT_BETS_KEY", "round:recent:bets")
    BETS_BY_CHAR_KEY = os.getenv(
        "REDIS_BETS_BY_CHAR_KEY",
        "round:current:bets:by_character",
    )
    BETS_BY_CHAR_COUNT_KEY = os.getenv(
        "REDIS_BETS_BY_CHAR_COUNT_KEY",
        "round:current:bets:by_character:count",
    )
    BETS_CHAR_NAMES_KEY = os.getenv(
        "REDIS_BETS_CHAR_NAMES_KEY",
        "round:current:bets:character_names",
    )

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = (
            redis_url
            or os.getenv(
                "BETS_REDIS_URL",
                os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")),
            )
        )

    def _client(self):
        return redis.Redis.from_url(self.redis_url, decode_responses=True)

    def load_recent_bets(self, limit: Optional[int] = 200) -> List[Dict]:
        """Load recent bettor activity from Redis list storage."""
        try:
            client = self._client()
            if limit is None:
                raw_rows = client.lrange(self.RECENT_BETS_KEY, 0, -1)
            else:
                raw_rows = client.lrange(self.RECENT_BETS_KEY, 0, max(0, limit - 1))
        except RedisError as exc:
            raise RealtimeBettingAnalysisError(str(exc)) from exc

        rows: List[Dict] = []
        for raw in raw_rows:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Skipping invalid recent bet payload: %s", raw)
                continue

            bettor_id = str(parsed.get("bettorName") or "").strip()
            option_code = str(parsed.get("optionCode") or "").strip().upper()
            amount = parsed.get("amount")
            if not bettor_id or not option_code:
                continue

            try:
                amount_value = float(amount)
            except (TypeError, ValueError):
                amount_value = 0.0

            rows.append(
                {
                    "bettor_id": bettor_id,
                    "option_code": option_code,
                    "amount": max(0.0, amount_value),
                    "placed_at": parsed.get("placedAt"),
                }
            )

        return rows

    def get_top_characters(self, limit: int = 5) -> List[Dict]:
        """Return the current top-bet characters for the active round."""
        try:
            client = self._client()
            totals = client.hgetall(self.BETS_BY_CHAR_KEY)
            counts = client.hgetall(self.BETS_BY_CHAR_COUNT_KEY)
            names = client.hgetall(self.BETS_CHAR_NAMES_KEY)
        except RedisError as exc:
            raise RealtimeBettingAnalysisError(str(exc)) from exc

        character_rows = []
        for field, raw_total in totals.items():
            if not field.endswith(":TOTAL"):
                continue

            try:
                character_id = int(field.split(":", 1)[0].lstrip("C"))
                total_stake = float(raw_total)
            except (TypeError, ValueError):
                continue

            total_count = counts.get(f"C{character_id}:TOTAL:COUNT", 0)
            try:
                total_count = int(total_count)
            except (TypeError, ValueError):
                total_count = 0

            character_rows.append(
                {
                    "character_id": character_id,
                    "character_name": names.get(str(character_id)) or f"Character #{character_id}",
                    "total_stake": total_stake,
                    "bet_count": total_count,
                }
            )

        total_pool = sum(row["total_stake"] for row in character_rows)
        for row in character_rows:
            row["pool_share_pct"] = (
                round((row["total_stake"] / total_pool) * 100, 2) if total_pool else 0.0
            )

        character_rows.sort(
            key=lambda row: (row["total_stake"], row["bet_count"]),
            reverse=True,
        )
        return character_rows[: max(1, limit)]

    def build_bettor_feature_rows(self, recent_bets: List[Dict]) -> List[BettorFeatureRow]:
        """Aggregate recent bets into clustering-ready bettor features."""
        by_bettor: Dict[str, List[Dict]] = defaultdict(list)
        for bet in recent_bets:
            by_bettor[bet["bettor_id"]].append(bet)

        feature_rows: List[BettorFeatureRow] = []
        for bettor_id, bets in by_bettor.items():
            stakes = np.array([bet["amount"] for bet in bets], dtype=np.float32)
            options = [bet["option_code"] for bet in bets]
            total_bets = len(bets)
            float_like = sum(1 for option in options if option.startswith("F"))
            double_like = sum(1 for option in options if "AND" in option)
            option_diversity = len(set(options)) / total_bets if total_bets else 0.0

            feature_vector = [
                float(total_bets),
                float(np.sum(stakes)) if len(stakes) else 0.0,
                float(np.mean(stakes)) if len(stakes) else 0.0,
                float(np.std(stakes)) if len(stakes) > 1 else 0.0,
                float(option_diversity),
                float(float_like / total_bets) if total_bets else 0.0,
                float(double_like / total_bets) if total_bets else 0.0,
            ]

            feature_rows.append(
                BettorFeatureRow(
                    bettor_id=bettor_id,
                    total_bets=total_bets,
                    total_stake=feature_vector[1],
                    average_stake=feature_vector[2],
                    stake_stddev=feature_vector[3],
                    option_diversity=feature_vector[4],
                    float_ratio=feature_vector[5],
                    double_ratio=feature_vector[6],
                    feature_vector=feature_vector,
                )
            )

        feature_rows.sort(key=lambda row: row.total_stake, reverse=True)
        return feature_rows

    def cluster_bettors(
        self,
        feature_rows: List[BettorFeatureRow],
        n_clusters: int = 3,
        random_state: int = 42,
    ) -> Dict:
        """Cluster bettors in memory and return human-readable summaries."""
        if len(feature_rows) < 2:
            return {
                "n_bettors": len(feature_rows),
                "n_clusters": 0,
                "clusters": [],
            }

        effective_clusters = max(2, min(n_clusters, len(feature_rows)))
        feature_matrix = np.array(
            [row.feature_vector for row in feature_rows],
            dtype=np.float32,
        )
        scaler = StandardScaler()
        feature_matrix_scaled = scaler.fit_transform(feature_matrix)

        model = KMeans(
            n_clusters=effective_clusters,
            random_state=random_state,
            n_init=10,
            max_iter=300,
        )
        labels = model.fit_predict(feature_matrix_scaled)

        clusters = []
        for cluster_id in range(effective_clusters):
            members = [
                row for row, label in zip(feature_rows, labels)
                if int(label) == cluster_id
            ]
            if not members:
                continue

            clusters.append(
                {
                    "cluster_id": cluster_id,
                    "size": len(members),
                    "avg_total_stake": round(float(np.mean([m.total_stake for m in members])), 2),
                    "avg_bets": round(float(np.mean([m.total_bets for m in members])), 2),
                    "avg_stake": round(float(np.mean([m.average_stake for m in members])), 2),
                    "avg_option_diversity": round(
                        float(np.mean([m.option_diversity for m in members])),
                        3,
                    ),
                    "sample_bettors": [m.bettor_id for m in members[:5]],
                }
            )

        clusters.sort(key=lambda row: row["avg_total_stake"], reverse=True)
        return {
            "n_bettors": len(feature_rows),
            "n_clusters": effective_clusters,
            "clusters": clusters,
        }

    def build_profile_histories(self, recent_bets: List[Dict]) -> Dict[str, List[Dict]]:
        """Convert live bet rows into histories compatible with BettorDataAggregator."""
        histories: Dict[str, List[Dict]] = defaultdict(list)
        for bet in recent_bets:
            option = bet["option_code"]
            if "AND" in option:
                bet_type = "combo"
            elif option.startswith("F"):
                bet_type = "float_single"
            else:
                bet_type = "drown_single"

            histories[bet["bettor_id"]].append(
                {
                    "amount": bet["amount"],
                    "bet_type": bet_type,
                    "outcome": None,
                    "payout": 0,
                    "round_id": 1,
                    "timestamp": bet.get("placed_at"),
                }
            )

        return histories
