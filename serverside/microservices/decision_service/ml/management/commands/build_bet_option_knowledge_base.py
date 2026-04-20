"""Build an exhaustive bet-option knowledge base dataset for ML."""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...models import BetOptionKnowledgeRow
from ...services.bet_option_knowledge_base import build_knowledge_rows


class Command(BaseCommand):
    help = (
        "Enumerate every supported virtual-betting option_code and build a per-character "
        "knowledge base (win probability + implied fair odds)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--version", default="v1", help="Dataset version key (default: v1)")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Delete existing rows for this version before rebuilding",
        )
        parser.add_argument(
            "--limit-characters",
            type=int,
            default=0,
            help="Only generate rows for the first N characters (debugging)",
        )
        parser.add_argument(
            "--export-csv",
            default="",
            help="Optional path to export a CSV after generating",
        )

    def handle(self, *args, **options):
        version = str(options["version"] or "v1").strip() or "v1"
        overwrite = bool(options["overwrite"])
        limit_characters = int(options["limit_characters"] or 0) or None
        export_csv = str(options["export_csv"] or "").strip()

        try:
            row_count = build_knowledge_rows(
                version=version,
                overwrite=overwrite,
                limit_characters=limit_characters,
            )
        except Exception as exc:
            raise CommandError(f"Knowledge base build failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Bet option knowledge base generated"))
        self.stdout.write(f"  Version: {version}")
        self.stdout.write(f"  Rows upserted: {row_count}")

        if not export_csv:
            return

        path = Path(export_csv).expanduser()
        if path.is_dir():
            raise CommandError("--export-csv must be a file path, not a directory")

        self._export_csv(version=version, path=path)
        self.stdout.write(self.style.SUCCESS(f"  Exported: {path}"))

    def _export_csv(self, *, version: str, path: Path) -> None:
        queryset = (
            BetOptionKnowledgeRow.objects.filter(version=version)
            .select_related("character", "option")
            .order_by("character_id", "option__option_code")
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "version",
                    "character_id",
                    "character_name",
                    "stamina",
                    "control",
                    "power",
                    "option_code",
                    "bet_type",
                    "float_phase",
                    "drown_phase",
                    "p_win",
                    "implied_fair_odds",
                    "p_float_phase1",
                    "p_float_phase2",
                    "p_float_phase3",
                    "p_float_phase4",
                    "p_float_phase5",
                ]
            )

            for row in queryset:
                probs = list(row.phase_float_probs or []) + [None] * 5
                probs = probs[:5]
                writer.writerow(
                    [
                        row.version,
                        row.character_id,
                        row.character.clean_name,
                        row.character.stamina,
                        row.character.control,
                        row.character.power,
                        row.option.option_code,
                        row.option.bet_type,
                        row.option.float_phase,
                        row.option.drown_phase,
                        row.p_win,
                        row.implied_fair_odds,
                        probs[0],
                        probs[1],
                        probs[2],
                        probs[3],
                        probs[4],
                    ]
                )
