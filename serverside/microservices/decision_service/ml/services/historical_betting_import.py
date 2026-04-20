"""Import bettor history from the client betting database into ML profiles."""
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db import connections

from Decision.models import Character, RoundMarketOutcome


class HistoricalBettingImportError(Exception):
    """Raised when historical betting data cannot be imported."""


class HistoricalBettingImporter:
    """Read real bettor history from the betting database and derive ML features."""

    BET_TABLE = "client_bet"

    @staticmethod
    def _quote(name: str) -> str:
        return '"' + str(name).replace('"', '""') + '"'

    def _resolve_client_bet_columns(self) -> Dict[str, Optional[str]]:
        with connections["betting"].cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                [self.BET_TABLE],
            )
            rows = cursor.fetchall()

        column_map = {str(row[0]).lower(): row[0] for row in rows}
        if not column_map:
            raise HistoricalBettingImportError(
                f"Table '{self.BET_TABLE}' was not found in the betting database."
            )

        def pick(exact_candidates: List[str], fuzzy_tokens: List[str]) -> Optional[str]:
            for candidate in exact_candidates:
                if candidate in column_map:
                    return column_map[candidate]
            for lower_name, actual_name in column_map.items():
                if any(token in lower_name for token in fuzzy_tokens):
                    return actual_name
            return None

        character = pick(["character_id", "character"], ["character"])
        game_round = pick(["game_round_id", "game_round"], ["game_round", "round"])
        if not character or not game_round:
            raise HistoricalBettingImportError(
                "Could not resolve required client_bet columns for character/game round."
            )

        return {
            "character": character,
            "game_round": game_round,
            "placed_at": column_map.get("placed_at"),
        }

    def load_client_bets(
        self,
        time_window_days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Load raw client bets from the betting database."""
        columns = self._resolve_client_bet_columns()
        character_col = self._quote(columns["character"])
        round_col = self._quote(columns["game_round"])
        placed_at_col = self._quote(columns["placed_at"]) if columns["placed_at"] else None

        query = f"""
            SELECT
                id,
                player_id,
                {character_col} AS character_id,
                {round_col} AS game_round_id,
                option_code,
                bet_type,
                phase_start,
                phase_end,
                stake,
                odds,
                status,
                {placed_at_col if placed_at_col else 'NOW()'} AS placed_at
            FROM {self._quote(self.BET_TABLE)}
        """

        where_clauses: List[str] = []
        params: List[object] = []
        if time_window_days:
            where_clauses.append(
                f"{placed_at_col if placed_at_col else 'NOW()'} >= NOW() - (%s * INTERVAL '1 day')"
            )
            params.append(time_window_days)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY placed_at DESC, id DESC"
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        with connections["betting"].cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns_out = [col[0] for col in cursor.description]

        return [dict(zip(columns_out, row)) for row in rows]

    @staticmethod
    def _derive_outcome_entries(option_code: str, phase_lookup: Dict[int, str]) -> List[Dict]:
        option = str(option_code or "").strip().upper()
        if not option:
            return []

        def resolve_selected_phase(selected_phase_number: int) -> Tuple[Optional[str], Optional[int]]:
            direct = str(phase_lookup.get(selected_phase_number) or "").upper()
            if direct:
                return direct, selected_phase_number

            terminal_drown_phase = None
            for phase_number, outcome_code in phase_lookup.items():
                if (
                    phase_number <= selected_phase_number
                    and str(outcome_code).upper() == "DROWN"
                    and (terminal_drown_phase is None or phase_number < terminal_drown_phase)
                ):
                    terminal_drown_phase = phase_number

            if terminal_drown_phase is not None:
                return "DROWN", terminal_drown_phase
            return None, None

        def build_entry(selected_outcome_code: str, phase_number: int) -> Dict:
            resolved_code, resolved_phase = resolve_selected_phase(phase_number)
            is_win = (
                resolved_code == selected_outcome_code and
                int(resolved_phase or 0) == int(phase_number)
            )
            return {
                "selected_outcome_code": selected_outcome_code,
                "phase_number": phase_number,
                "resolved_outcome_code": resolved_code,
                "resolved_phase_number": resolved_phase,
                "status": "pending" if not resolved_code else ("won" if is_win else "lost"),
            }

        if len(option) == 2 and option[0] in {"F", "D"} and option[1].isdigit():
            phase_number = int(option[1])
            return [build_entry("FLOAT" if option[0] == "F" else "DROWN", phase_number)]

        normalized = option.replace(" ", "")
        if normalized.startswith("F") and "ANDD" in normalized:
            float_phase_str, drown_phase_str = normalized[1:].split("ANDD", 1)
            if float_phase_str.isdigit() and drown_phase_str.isdigit():
                float_phase = int(float_phase_str)
                drown_phase = int(drown_phase_str)
                return [
                    build_entry("FLOAT", float_phase),
                    build_entry("DROWN", drown_phase),
                ]

        return []

    def _build_resolved_lookup(self, client_bets: List[Dict]) -> Dict[Tuple[int, int], Dict[int, str]]:
        round_ids = sorted({
            int(row["game_round_id"])
            for row in client_bets
            if row.get("game_round_id") is not None
        })
        character_ids = sorted({
            int(row["character_id"])
            for row in client_bets
            if row.get("character_id") is not None
        })
        if not round_ids or not character_ids:
            return {}

        queryset = RoundMarketOutcome.objects.filter(
            client_round_id__in=round_ids,
            character_id__in=character_ids,
        ).select_related("outcome").order_by("client_round_id", "character_id", "phase_number")

        lookup: Dict[Tuple[int, int], Dict[int, str]] = defaultdict(dict)
        for row in queryset:
            if row.outcome_id:
                lookup[(row.client_round_id, row.character_id)][row.phase_number] = row.outcome.code
        return lookup

    @staticmethod
    def _decimal_to_float(value: object) -> float:
        if isinstance(value, Decimal):
            return float(value)
        if value is None:
            return 0.0
        return float(value)

    def build_bettor_histories(
        self,
        time_window_days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
        """Return histories keyed by bettor_id plus top-character aggregate rows."""
        client_bets = self.load_client_bets(
            time_window_days=time_window_days,
            limit=limit,
        )
        resolved_lookup = self._build_resolved_lookup(client_bets)
        character_names = {}
        for row in Character.objects.values("id", "name"):
            character_names[row["id"]] = str(row["name"]).split("_", 1)[0]

        histories: Dict[str, List[Dict]] = defaultdict(list)
        character_totals: Dict[int, Dict[str, object]] = defaultdict(
            lambda: {"total_stake": 0.0, "bet_count": 0}
        )

        for row in client_bets:
            player_id = row.get("player_id")
            character_id = row.get("character_id")
            round_id = row.get("game_round_id")
            if player_id is None or character_id is None or round_id is None:
                continue

            stake = self._decimal_to_float(row.get("stake"))
            odds = self._decimal_to_float(row.get("odds"))
            phase_lookup = resolved_lookup.get((int(round_id), int(character_id)), {})
            outcome_entries = self._derive_outcome_entries(row.get("option_code"), phase_lookup)

            if outcome_entries and any(entry["status"] == "lost" for entry in outcome_entries):
                outcome = "loss"
                payout = 0.0
            elif outcome_entries and all(entry["status"] == "won" for entry in outcome_entries):
                outcome = "win"
                payout = round(stake * odds, 2)
            else:
                outcome = None
                payout = 0.0

            option_code = str(row.get("option_code") or "").upper()
            if "AND" in option_code:
                bet_type = "combo"
            elif option_code.startswith("F"):
                bet_type = "float_single"
            elif option_code.startswith("D"):
                bet_type = "drown_single"
            else:
                bet_type = str(row.get("bet_type") or "unknown").lower()

            bettor_id = str(player_id)
            histories[bettor_id].append(
                {
                    "amount": stake,
                    "bet_type": bet_type,
                    "outcome": outcome,
                    "payout": payout,
                    "round_id": int(round_id),
                    "timestamp": row.get("placed_at"),
                    "character_id": int(character_id),
                    "option_code": option_code,
                }
            )

            character_totals[int(character_id)]["total_stake"] += stake
            character_totals[int(character_id)]["bet_count"] += 1

        top_characters = []
        for character_id, totals in character_totals.items():
            top_characters.append(
                {
                    "character_id": character_id,
                    "character_name": character_names.get(character_id, f"Character #{character_id}"),
                    "total_stake": round(float(totals["total_stake"]), 2),
                    "bet_count": int(totals["bet_count"]),
                }
            )
        top_characters.sort(
            key=lambda row: (row["total_stake"], row["bet_count"]),
            reverse=True,
        )

        return histories, top_characters
