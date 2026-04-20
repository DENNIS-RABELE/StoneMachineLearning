from django.core.management.base import BaseCommand, CommandError

from Betdata.models import Outcome, OutcomeKind, Phase


class Command(BaseCommand):
    help = "Seed client phases and outcomes for the betting data service."

    def add_arguments(self, parser):
        parser.add_argument(
            "--phases",
            type=int,
            default=5,
            help="Number of phases to seed (default: 5).",
        )

    def handle(self, *args, **options):
        phase_count = max(1, int(options["phases"] or 5))

        try:
            for number in range(1, phase_count + 1):
                phase, _ = Phase.objects.update_or_create(
                    number=number,
                    defaults={"name": f"Phase {number}"},
                )

                float_external_id = number * 2 - 1
                drown_external_id = number * 2

                Outcome.objects.update_or_create(
                    external_outcome_id=float_external_id,
                    defaults={
                        "phase_id": phase.number,
                        "kind": OutcomeKind.FLOAT,
                        "code": f"F{number}",
                        "label": f"Float {number}",
                    },
                )
                Outcome.objects.update_or_create(
                    external_outcome_id=drown_external_id,
                    defaults={
                        "phase_id": phase.number,
                        "kind": OutcomeKind.DROWN,
                        "code": f"D{number}",
                        "label": f"Drown {number}",
                    },
                )
        except Exception as exc:
            raise CommandError(f"Failed to seed client bet data: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {phase_count} phases and {phase_count * 2} outcomes."
            )
        )
