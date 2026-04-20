"""Sync real bettor history, train k-means, and print top characters."""
from django.core.management.base import BaseCommand, CommandError

from ...models import BettorProfile
from ...services.data_preprocessing import BettorDataAggregator
from ...services.historical_betting_import import (
    HistoricalBettingImportError,
    HistoricalBettingImporter,
)
from ...services.kmeans_clustering import KMeansBettorClusterer


class Command(BaseCommand):
    help = "Analyze real bettor history from client_bet, sync profiles, and train k-means"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clusters",
            type=int,
            default=4,
            help="Number of k-means clusters (default: 4)",
        )
        parser.add_argument(
            "--model-name",
            type=str,
            default="historical_behavior_model",
            help="Saved clustering model name (default: historical_behavior_model)",
        )
        parser.add_argument(
            "--time-window-days",
            type=int,
            default=None,
            help="Only import bets from the last N days",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit imported bet rows for testing",
        )
        parser.add_argument(
            "--clear-existing-profiles",
            action="store_true",
            help="Clear BettorProfile rows before syncing",
        )

    def handle(self, *args, **options):
        importer = HistoricalBettingImporter()

        try:
            histories, top_characters = importer.build_bettor_histories(
                time_window_days=options["time_window_days"],
                limit=options["limit"],
            )
        except HistoricalBettingImportError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Historical import failed: {exc}") from exc

        if options["clear_existing_profiles"]:
            BettorProfile.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing BettorProfile rows."))

        profiles = BettorDataAggregator.batch_update_profiles(
            bettor_betting_data=histories,
            time_window_days=options["time_window_days"],
        )

        self.stdout.write(self.style.SUCCESS("Historical Betting Analysis"))
        self.stdout.write(f"  Imported bettors: {len(histories)}")
        self.stdout.write(f"  Synced profiles: {len(profiles)}")

        if top_characters:
            total_stake = sum(row["total_stake"] for row in top_characters)
            self.stdout.write("\nMost-bet characters:")
            for index, row in enumerate(top_characters[:5], start=1):
                share = (row["total_stake"] / total_stake * 100) if total_stake else 0.0
                self.stdout.write(
                    f"  {index}. {row['character_name']} "
                    f"(id={row['character_id']}, stake={row['total_stake']:.2f}, "
                    f"bets={row['bet_count']}, share={share:.2f}%)"
                )

        if len(profiles) < max(2, options["clusters"]):
            self.stdout.write(
                self.style.WARNING(
                    "\nNot enough synced bettor profiles to train k-means yet."
                )
            )
            return

        clusterer = KMeansBettorClusterer(n_clusters=options["clusters"])
        model = clusterer.train(
            model_name=options["model_name"],
            description="Trained from real client_bet history imported into decision_service",
        )
        summary = clusterer.get_all_clusters_summary(model)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTrained model '{model.name}' with {model.num_samples_trained} bettors."
            )
        )
        silhouette = (
            f"{model.silhouette_score:.4f}"
            if model.silhouette_score is not None
            else "n/a"
        )
        davies_bouldin = (
            f"{model.davies_bouldin_score:.4f}"
            if model.davies_bouldin_score is not None
            else "n/a"
        )
        self.stdout.write(
            f"  Silhouette: {silhouette} | "
            f"Davies-Bouldin: {davies_bouldin} | "
            f"Inertia: {model.inertia:.4f}"
        )
        self.stdout.write("\nCluster summaries:")
        for cluster in summary["clusters"]:
            self.stdout.write(
                f"  Cluster {cluster['cluster_id']}: {cluster['profile_name']} "
                f"(size={cluster['cluster_size']}, avg_win_rate={cluster['avg_win_rate']:.2%}, "
                f"avg_roi={cluster['avg_roi']:.2f}%, avg_bet={cluster['avg_bet_amount']:.2f})"
            )
