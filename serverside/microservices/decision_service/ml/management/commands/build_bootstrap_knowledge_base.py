"""Build an initial virtual-betting knowledge base from Monte Carlo simulation."""
from django.core.management.base import BaseCommand, CommandError

from ...services.data_preprocessing import BettorDataAggregator
from ...services.kmeans_clustering import KMeansBettorClusterer
from ...services.monte_carlo_simulation import MonteCarloKnowledgeBaseBuilder


class Command(BaseCommand):
    help = (
        "Generate a Monte Carlo bootstrap knowledge base, sync synthetic bettors, "
        "and optionally train a clustering model from the synthetic dataset."
    )

    def add_arguments(self, parser):
        parser.add_argument("--simulation-name", required=True, help="Name for the simulation run")
        parser.add_argument(
            "--model-name",
            default="",
            help="Optional clustering model name to train after syncing bettors",
        )
        parser.add_argument("--rounds", type=int, default=500, help="Rounds to simulate")
        parser.add_argument("--bettors", type=int, default=100, help="Synthetic bettors to simulate")
        parser.add_argument(
            "--characters-per-round",
            type=int,
            default=5,
            help="How many characters appear in each simulated round",
        )
        parser.add_argument("--clusters", type=int, default=4, help="Clusters for the bootstrap model")
        parser.add_argument("--seed", type=int, default=42, help="Random seed")
        parser.add_argument(
            "--skip-clustering",
            action="store_true",
            help="Only build and sync the knowledge base without training k-means",
        )

    def handle(self, *args, **options):
        rounds = options["rounds"]
        bettors = options["bettors"]
        if rounds < 1 or bettors < 1:
            raise CommandError("rounds and bettors must be positive integers")

        builder = MonteCarloKnowledgeBaseBuilder(seed=options["seed"])
        try:
            result = builder.run(
                run_name=options["simulation_name"],
                rounds=rounds,
                bettors=bettors,
                characters_per_round=options["characters_per_round"],
            )
        except Exception as exc:
            raise CommandError(f"Bootstrap simulation failed: {exc}") from exc

        simulation_run = result["simulation_run"]
        histories = result["bettor_histories"]
        strategy_rows = result["strategy_summaries"]

        profiles = BettorDataAggregator.batch_update_profiles(histories)

        self.stdout.write(self.style.SUCCESS("Bootstrap knowledge base generated"))
        self.stdout.write(f"  Simulation run: {simulation_run.name}")
        self.stdout.write(f"  Rounds simulated: {simulation_run.rounds_simulated}")
        self.stdout.write(f"  Synthetic bettors: {simulation_run.bettors_simulated}")
        self.stdout.write(f"  Synced BettorProfile rows: {len(profiles)}")
        self.stdout.write(f"  Total stake: {simulation_run.total_stake:.2f}")
        self.stdout.write(f"  Total payout: {simulation_run.total_payout:.2f}")
        self.stdout.write(f"  Average ROI: {simulation_run.average_roi:.2f}%")

        self.stdout.write("\nStrategy insights:")
        for row in strategy_rows:
            self.stdout.write(
                f"  {row['strategy_name']}: roi={row['average_roi']:.2f}%, "
                f"win_rate={row['average_win_rate']:.2%}, avg_stake={row['average_stake']:.2f}, "
                f"top_character={row['top_character_name'] or 'n/a'}"
            )

        if options["skip_clustering"]:
            return

        model_name = options["model_name"] or f"{simulation_run.name}_clusters"
        if len(profiles) < options["clusters"]:
            raise CommandError(
                f"Need at least {options['clusters']} profiles to train, but only {len(profiles)} were synced"
            )

        try:
            clusterer = KMeansBettorClusterer(
                n_clusters=options["clusters"],
                random_state=options["seed"],
            )
            trained_model = clusterer.train(
                model_name=model_name,
                description=(
                    f"Bootstrap model generated from simulation run {simulation_run.name}"
                ),
            )
        except Exception as exc:
            raise CommandError(f"Bootstrap clustering failed: {exc}") from exc

        silhouette = (
            f"{trained_model.silhouette_score:.4f}"
            if trained_model.silhouette_score is not None
            else "n/a"
        )
        self.stdout.write(self.style.SUCCESS("\nBootstrap clustering model trained"))
        self.stdout.write(f"  Model: {trained_model.name}")
        self.stdout.write(f"  Samples trained: {trained_model.num_samples_trained}")
        self.stdout.write(f"  Clusters: {trained_model.n_clusters}")
        self.stdout.write(f"  Silhouette: {silhouette}")
