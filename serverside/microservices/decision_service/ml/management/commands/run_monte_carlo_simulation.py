"""Generate a Monte Carlo bootstrap knowledge base for virtual betting."""
from django.core.management.base import BaseCommand, CommandError

from ...services.data_preprocessing import BettorDataAggregator
from ...services.monte_carlo_simulation import MonteCarloKnowledgeBaseBuilder


class Command(BaseCommand):
    help = "Run Monte Carlo simulations to generate an initial virtual-betting knowledge base"

    def add_arguments(self, parser):
        parser.add_argument("--name", type=str, required=True, help="Simulation run name")
        parser.add_argument("--rounds", type=int, default=500, help="Rounds to simulate (default: 500)")
        parser.add_argument("--bettors", type=int, default=100, help="Synthetic bettors to simulate (default: 100)")
        parser.add_argument(
            "--characters-per-round",
            type=int,
            default=5,
            help="How many characters appear per simulated round (default: 5)",
        )
        parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
        parser.add_argument(
            "--sync-bettor-profiles",
            action="store_true",
            help="Sync the simulated bettor histories into BettorProfile rows",
        )

    def handle(self, *args, **options):
        if options["rounds"] < 1 or options["bettors"] < 1:
            raise CommandError("rounds and bettors must be positive integers")

        builder = MonteCarloKnowledgeBaseBuilder(seed=options["seed"])
        try:
            result = builder.run(
                run_name=options["name"],
                rounds=options["rounds"],
                bettors=options["bettors"],
                characters_per_round=options["characters_per_round"],
            )
        except Exception as exc:
            raise CommandError(f"Monte Carlo simulation failed: {exc}") from exc

        simulation_run = result["simulation_run"]
        histories = result["bettor_histories"]
        strategy_rows = result["strategy_summaries"]

        self.stdout.write(self.style.SUCCESS("Monte Carlo simulation completed"))
        self.stdout.write(f"  Run: {simulation_run.name}")
        self.stdout.write(f"  Rounds simulated: {simulation_run.rounds_simulated}")
        self.stdout.write(f"  Bettors simulated: {simulation_run.bettors_simulated}")
        self.stdout.write(f"  Total stake: {simulation_run.total_stake:.2f}")
        self.stdout.write(f"  Total payout: {simulation_run.total_payout:.2f}")
        self.stdout.write(f"  Average ROI: {simulation_run.average_roi:.2f}%")
        self.stdout.write(f"  Average win rate: {simulation_run.average_win_rate:.2%}")

        self.stdout.write("\nStrategy knowledge base:")
        for row in strategy_rows:
            self.stdout.write(
                f"  {row['strategy_name']}: roi={row['average_roi']:.2f}%, "
                f"win_rate={row['average_win_rate']:.2%}, avg_stake={row['average_stake']:.2f}, "
                f"top_character={row['top_character_name'] or 'n/a'}"
            )

        if options["sync_bettor_profiles"]:
            profiles = BettorDataAggregator.batch_update_profiles(histories)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSynced {len(profiles)} simulated bettor profiles into the ML app."
                )
            )
