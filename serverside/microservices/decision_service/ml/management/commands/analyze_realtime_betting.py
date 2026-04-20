"""Analyze current bettor behavior with k-means and report top-bet characters."""
from django.core.management.base import BaseCommand, CommandError

from ...services.data_preprocessing import BettorDataAggregator
from ...services.realtime_behavior_analysis import (
    RealtimeBettingAnalysisError,
    RealtimeBettingAnalyzer,
)


class Command(BaseCommand):
    help = "Cluster live bettor behavior from Redis recent bets and show most-bet characters"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clusters",
            type=int,
            default=3,
            help="Requested number of bettor clusters (default: 3)",
        )
        parser.add_argument(
            "--recent-limit",
            type=int,
            default=200,
            help="Number of recent bets to analyze from Redis (default: 200)",
        )
        parser.add_argument(
            "--top-characters",
            type=int,
            default=5,
            help="How many top characters to show (default: 5)",
        )
        parser.add_argument(
            "--sync-profiles",
            action="store_true",
            help="Also sync provisional BettorProfile rows from live recent bets",
        )

    def handle(self, *args, **options):
        analyzer = RealtimeBettingAnalyzer()

        try:
            recent_bets = analyzer.load_recent_bets(limit=options["recent_limit"])
            top_characters = analyzer.get_top_characters(limit=options["top_characters"])
        except RealtimeBettingAnalysisError as exc:
            raise CommandError(f"Redis analysis failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Realtime Betting Analysis"))
        self.stdout.write(f"  Recent bets loaded: {len(recent_bets)}")

        if top_characters:
            self.stdout.write("\nTop characters by current stake:")
            for index, row in enumerate(top_characters, start=1):
                self.stdout.write(
                    f"  {index}. {row['character_name']} "
                    f"(id={row['character_id']}, stake={row['total_stake']:.2f}, "
                    f"bets={row['bet_count']}, share={row['pool_share_pct']:.2f}%)"
                )
        else:
            self.stdout.write("\nNo character stake data found in Redis.")

        if not recent_bets:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo recent bettor events were found, so k-means clustering was skipped."
                )
            )
            return

        feature_rows = analyzer.build_bettor_feature_rows(recent_bets)
        clustering = analyzer.cluster_bettors(
            feature_rows,
            n_clusters=options["clusters"],
        )

        self.stdout.write(
            f"\nBettor clustering: {clustering['n_bettors']} bettors "
            f"across {clustering['n_clusters']} clusters"
        )
        for cluster in clustering["clusters"]:
            self.stdout.write(
                f"  Cluster {cluster['cluster_id']}: size={cluster['size']}, "
                f"avg_total_stake={cluster['avg_total_stake']:.2f}, "
                f"avg_bets={cluster['avg_bets']:.2f}, "
                f"avg_stake={cluster['avg_stake']:.2f}, "
                f"diversity={cluster['avg_option_diversity']:.3f}"
            )
            self.stdout.write(
                f"    Sample bettors: {', '.join(cluster['sample_bettors'])}"
            )

        if options["sync_profiles"]:
            histories = analyzer.build_profile_histories(recent_bets)
            profiles = BettorDataAggregator.batch_update_profiles(histories)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSynced {len(profiles)} provisional BettorProfile rows from live bets."
                )
            )
