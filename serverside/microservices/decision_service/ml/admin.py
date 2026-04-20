from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    BettorProfile,
    ClusteringModel,
    BettorCluster,
    ClusterCharacteristics,
    MLMetrics,
    MonteCarloSimulationRun,
    MonteCarloStrategyInsight,
    BetOptionDefinition,
    BetOptionKnowledgeRow,
    RoundBettingSnapshot,
)
from .services.dashboard_visuals import make_bar_chart_svg, make_scatter_svg


class BettorClusterInline(admin.TabularInline):
    model = BettorCluster
    extra = 0
    can_delete = False
    fields = ("bettor_profile", "cluster_id", "confidence", "assigned_at")
    readonly_fields = fields
    show_change_link = True
    verbose_name_plural = "Bettor Membership"


class ClusterCharacteristicsInline(admin.TabularInline):
    model = ClusterCharacteristics
    extra = 0
    can_delete = False
    fields = (
        "cluster_id",
        "profile_name",
        "cluster_size",
        "avg_win_rate",
        "avg_roi",
        "avg_bet_amount",
    )
    readonly_fields = fields
    verbose_name_plural = "Cluster Summary"


class MonteCarloStrategyInsightInline(admin.TabularInline):
    model = MonteCarloStrategyInsight
    extra = 0
    can_delete = False
    fields = (
        "strategy_name",
        "sample_size",
        "average_roi",
        "average_win_rate",
        "average_stake",
        "top_character_name",
        "top_character_share",
    )
    readonly_fields = fields
    verbose_name_plural = "Strategy Insights"


@admin.register(BettorProfile)
class BettorProfileAdmin(admin.ModelAdmin):
    list_display = ("bettor_id", "win_rate", "total_bets", "roi", "last_updated")
    search_fields = ("bettor_id",)
    list_filter = ("total_bets", "win_rate", "roi")
    ordering = ("-last_updated",)


@admin.register(ClusteringModel)
class ClusteringModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "n_clusters",
        "num_samples_trained",
        "is_active",
        "trained_at",
    )
    list_filter = ("is_active", "n_clusters")
    search_fields = ("name",)
    ordering = ("-trained_at",)
    inlines = (ClusterCharacteristicsInline,)
    readonly_fields = (
        "trained_at",
        "last_evaluated",
        "visual_overview",
        "cluster_size_visual",
        "cluster_roi_visual",
        "confidence_scatter_visual",
    )
    fieldsets = (
        (
            "Visual Insights",
            {
                "fields": (
                    "visual_overview",
                    "cluster_size_visual",
                    "cluster_roi_visual",
                    "confidence_scatter_visual",
                )
            },
        ),
        (
            "Model Snapshot",
            {
                "fields": (
                    "name",
                    "n_clusters",
                    "num_samples_trained",
                    "is_active",
                    "trained_at",
                    "description",
                )
            },
        ),
        (
            "Performance Summary",
            {
                "fields": (
                    "silhouette_score",
                    "davies_bouldin_score",
                    "inertia",
                    "last_evaluated",
                )
            },
        ),
        (
            "Configuration",
            {
                "classes": ("collapse",),
                "fields": (
                    "random_state",
                    "max_iterations",
                    "n_init",
                    "features_used",
                )
            },
        ),
        (
            "Advanced Data",
            {
                "classes": ("collapse",),
                "fields": (
                    "model_params",
                )
            },
        ),
    )

    def _cluster_rows(self, obj):
        if not obj:
            return []
        return list(obj.cluster_characteristics.order_by("cluster_id"))

    def visual_overview(self, obj):
        if not obj or not obj.pk:
            return "Save the model first to view charts."
        silhouette = (
            f"{obj.silhouette_score:.4f}"
            if obj.silhouette_score is not None
            else "n/a"
        )
        davies_bouldin = (
            f"{obj.davies_bouldin_score:.4f}"
            if obj.davies_bouldin_score is not None
            else "n/a"
        )
        cluster_rows = self._cluster_rows(obj)
        top_cluster = max(cluster_rows, key=lambda row: row.cluster_size, default=None)
        top_cluster_label = top_cluster.profile_name if top_cluster else "No cluster summary yet"
        html = f"""
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;max-width:860px;margin:6px 0 10px;">
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#fff7ed,#ffedd5);border:1px solid #fed7aa;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#9a3412;">Samples</div>
                <div style="font-size:28px;font-weight:700;color:#7c2d12;margin-top:8px;">{obj.num_samples_trained}</div>
            </div>
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#ecfeff,#ccfbf1);border:1px solid #99f6e4;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#0f766e;">Clusters</div>
                <div style="font-size:28px;font-weight:700;color:#115e59;margin-top:8px;">{obj.n_clusters}</div>
            </div>
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#eff6ff,#dbeafe);border:1px solid #bfdbfe;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#1d4ed8;">Silhouette</div>
                <div style="font-size:28px;font-weight:700;color:#1e3a8a;margin-top:8px;">{silhouette}</div>
            </div>
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#fdf2f8,#fce7f3);border:1px solid #fbcfe8;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#be185d;">Largest Cluster</div>
                <div style="font-size:18px;font-weight:700;color:#831843;margin-top:10px;line-height:1.2;">{top_cluster_label}</div>
            </div>
        </div>
        """
        return mark_safe(html)

    visual_overview.short_description = "Overview"

    def cluster_size_visual(self, obj):
        if not obj or not obj.pk:
            return "Save the model first to view cluster visuals."
        items = [
            (
                f"Cluster {row.cluster_id} {row.profile_name or ''}".strip(),
                float(row.cluster_size),
            )
            for row in self._cluster_rows(obj)
        ]
        svg = make_bar_chart_svg(items, "Cluster Sizes", color="#0f766e")
        return format_html('<div style="max-width:840px;overflow:auto;padding:6px 0 2px;">{}</div>', mark_safe(svg))

    cluster_size_visual.short_description = "Cluster Size Chart"

    def cluster_roi_visual(self, obj):
        if not obj or not obj.pk:
            return "Save the model first to view ROI visuals."
        items = [
            (
                f"Cluster {row.cluster_id}",
                float(row.avg_roi),
            )
            for row in self._cluster_rows(obj)
        ]
        svg = make_bar_chart_svg(items, "Average ROI by Cluster", color="#c2410c")
        return format_html('<div style="max-width:840px;overflow:auto;padding:6px 0 2px;">{}</div>', mark_safe(svg))

    cluster_roi_visual.short_description = "Cluster ROI Chart"

    def confidence_scatter_visual(self, obj):
        if not obj or not obj.pk:
            return "Save the model first to view bettor behavior visuals."
        assignments = list(
            obj.bettor_clusters.select_related("bettor_profile").order_by("-confidence")[:100]
        )
        points = [
            {
                "bettor_id": assignment.bettor_profile.bettor_id,
                "average_bet_amount": assignment.bettor_profile.average_bet_amount,
                "roi": assignment.bettor_profile.roi,
                "total_bets": assignment.bettor_profile.total_bets,
            }
            for assignment in assignments
        ]
        svg = make_scatter_svg(points, "Bettor ROI vs Average Bet")
        return format_html('<div style="max-width:840px;overflow:auto;padding:6px 0 2px;">{}</div>', mark_safe(svg))

    confidence_scatter_visual.short_description = "Bettor Scatter Plot"


@admin.register(BettorCluster)
class BettorClusterAdmin(admin.ModelAdmin):
    list_display = ("bettor_profile", "model", "cluster_id", "confidence", "assigned_at")
    list_filter = ("cluster_id", "model")
    search_fields = ("bettor_profile__bettor_id",)
    ordering = ("-assigned_at",)


@admin.register(ClusterCharacteristics)
class ClusterCharacteristicsAdmin(admin.ModelAdmin):
    list_display = ("model", "cluster_id", "cluster_size", "avg_win_rate", "avg_roi")
    list_filter = ("model",)
    search_fields = ("profile_name",)
    ordering = ("-cluster_size",)


@admin.register(MLMetrics)
class MLMetricsAdmin(admin.ModelAdmin):
    list_display = ("model", "metric_type", "value", "timestamp")
    list_filter = ("metric_type", "model")
    ordering = ("-timestamp",)


@admin.register(MonteCarloSimulationRun)
class MonteCarloSimulationRunAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "rounds_simulated",
        "bettors_simulated",
        "average_roi",
        "created_at",
    )
    search_fields = ("name",)
    ordering = ("-created_at",)
    inlines = (MonteCarloStrategyInsightInline,)
    readonly_fields = (
        "created_at",
        "simulation_overview",
        "strategy_roi_visual",
        "strategy_character_visual",
    )
    fieldsets = (
        (
            "Knowledge Base Visuals",
            {
                "fields": (
                    "simulation_overview",
                    "strategy_roi_visual",
                    "strategy_character_visual",
                )
            },
        ),
        (
            "Run Snapshot",
            {
                "fields": (
                    "name",
                    "description",
                    "rounds_simulated",
                    "bettors_simulated",
                    "characters_per_round",
                    "random_seed",
                    "created_at",
                )
            },
        ),
        (
            "Performance",
            {
                "fields": (
                    "average_roi",
                    "average_win_rate",
                    "total_stake",
                    "total_payout",
                )
            },
        ),
        (
            "Knowledge Base Data",
            {
                "classes": ("collapse",),
                "fields": ("knowledge_base", "strategies_used"),
            },
        ),
    )

    def simulation_overview(self, obj):
        if not obj or not obj.pk:
            return "Save the simulation run first to view the bootstrap summary."
        strategy_count = obj.strategy_insights.count()
        best_strategy = obj.strategy_insights.order_by("-average_roi").first()
        html = f"""
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;max-width:860px;margin:6px 0 10px;">
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#fff7ed,#ffedd5);border:1px solid #fed7aa;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#9a3412;">Rounds</div>
                <div style="font-size:28px;font-weight:700;color:#7c2d12;margin-top:8px;">{obj.rounds_simulated}</div>
            </div>
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#ecfeff,#ccfbf1);border:1px solid #99f6e4;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#0f766e;">Synthetic Bettors</div>
                <div style="font-size:28px;font-weight:700;color:#115e59;margin-top:8px;">{obj.bettors_simulated}</div>
            </div>
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#eff6ff,#dbeafe);border:1px solid #bfdbfe;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#1d4ed8;">Strategy Rows</div>
                <div style="font-size:28px;font-weight:700;color:#1e3a8a;margin-top:8px;">{strategy_count}</div>
            </div>
            <div style="padding:16px 18px;border-radius:20px;background:linear-gradient(135deg,#fdf2f8,#fce7f3);border:1px solid #fbcfe8;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#be185d;">Best Strategy</div>
                <div style="font-size:18px;font-weight:700;color:#831843;margin-top:10px;line-height:1.2;">{best_strategy.strategy_name if best_strategy else 'n/a'}</div>
            </div>
        </div>
        """
        return mark_safe(html)

    simulation_overview.short_description = "Overview"

    def strategy_roi_visual(self, obj):
        if not obj or not obj.pk:
            return "Save the simulation run first to view strategy ROI."
        items = [
            (row.strategy_name.replace("_", " ").title(), float(row.average_roi))
            for row in obj.strategy_insights.order_by("-average_roi")
        ]
        svg = make_bar_chart_svg(items, "Strategy ROI", color="#b45309")
        return format_html('<div style="max-width:840px;overflow:auto;padding:6px 0 2px;">{}</div>', mark_safe(svg))

    strategy_roi_visual.short_description = "ROI by Strategy"

    def strategy_character_visual(self, obj):
        if not obj or not obj.pk:
            return "Save the simulation run first to view character preference trends."
        items = [
            (
                row.top_character_name or row.strategy_name.replace("_", " ").title(),
                float(row.top_character_share),
            )
            for row in obj.strategy_insights.order_by("-top_character_share")
            if row.top_character_name or row.top_character_share
        ]
        svg = make_bar_chart_svg(items, "Top Character Share by Strategy", color="#0f766e")
        return format_html('<div style="max-width:840px;overflow:auto;padding:6px 0 2px;">{}</div>', mark_safe(svg))

    strategy_character_visual.short_description = "Character Preference"


@admin.register(MonteCarloStrategyInsight)
class MonteCarloStrategyInsightAdmin(admin.ModelAdmin):
    list_display = (
        "simulation_run",
        "strategy_name",
        "average_roi",
        "average_win_rate",
        "top_character_name",
    )
    list_filter = ("simulation_run", "strategy_name")
    ordering = ("-average_roi",)


@admin.register(BetOptionDefinition)
class BetOptionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("option_code", "bet_type", "float_phase", "drown_phase", "is_combo")
    list_filter = ("bet_type", "is_combo")
    search_fields = ("option_code",)
    ordering = ("option_code",)


@admin.register(BetOptionKnowledgeRow)
class BetOptionKnowledgeRowAdmin(admin.ModelAdmin):
    list_display = ("version", "character", "option", "p_win", "implied_fair_odds", "generated_at")
    list_filter = ("version", "option__bet_type")
    search_fields = ("character__name", "option__option_code")
    ordering = ("-generated_at",)


@admin.register(RoundBettingSnapshot)
class RoundBettingSnapshotAdmin(admin.ModelAdmin):
    list_display = ("round_id", "total_bets", "total_pool", "captured_at")
    list_filter = ("round_id",)
    search_fields = ("round_id",)
    ordering = ("-captured_at",)
    readonly_fields = (
        "round_id",
        "game_round_pk",
        "captured_at",
        "total_pool",
        "total_bets",
        "top_characters",
        "top_phases_live",
        "top_options",
        "top_combos",
        "top_phases_selected",
        "thresholds",
        "source",
    )
