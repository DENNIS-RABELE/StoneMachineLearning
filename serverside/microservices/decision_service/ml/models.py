"""
Machine Learning models for betting behavior analysis using k-means clustering.
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField
import json


class BettorProfile(models.Model):
    """Stores aggregated bettor betting history for ML analysis."""
    bettor_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Behavioral features
    total_bets = models.PositiveIntegerField(default=0)
    total_wins = models.PositiveIntegerField(default=0)
    total_losses = models.PositiveIntegerField(default=0)
    win_rate = models.FloatField(default=0.0)
    
    # Risk profile
    average_bet_amount = models.FloatField(default=0.0)
    max_bet_amount = models.FloatField(default=0.0)
    min_bet_amount = models.FloatField(default=0.0)
    bet_variance = models.FloatField(default=0.0)
    
    # Timing patterns
    average_bets_per_round = models.FloatField(default=0.0)
    total_active_rounds = models.PositiveIntegerField(default=0)
    
    # Strategy patterns
    favorite_bet_type = models.CharField(max_length=50, blank=True)
    strategy_diversity = models.FloatField(default=0.0)  # 0-1, how diverse their strategies are
    
    # Performance
    total_profit = models.FloatField(default=0.0)
    roi = models.FloatField(default=0.0)  # Return on investment
    
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "bettor_profiles"
        indexes = [
            models.Index(fields=['bettor_id', 'last_updated']),
            models.Index(fields=['win_rate']),
            models.Index(fields=['roi']),
        ]
    
    def __str__(self):
        return f"Bettor {self.bettor_id} - Win Rate: {self.win_rate:.2%}"


class ClusteringModel(models.Model):
    """Stores metadata about trained clustering models."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Model configuration
    n_clusters = models.PositiveSmallIntegerField()
    random_state = models.PositiveIntegerField(default=42)
    max_iterations = models.PositiveIntegerField(default=300)
    n_init = models.PositiveIntegerField(default=10)
    
    # Training data info
    num_samples_trained = models.PositiveIntegerField()
    features_used = ArrayField(
        models.CharField(max_length=100),
        help_text="List of feature names used for clustering"
    )
    
    # Model performance
    inertia = models.FloatField(null=True, blank=True)
    silhouette_score = models.FloatField(null=True, blank=True)
    davies_bouldin_score = models.FloatField(null=True, blank=True)
    
    # Model state (serialized)
    model_params = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=False)
    trained_at = models.DateTimeField(auto_now_add=True)
    last_evaluated = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "clustering_models"
        ordering = ['-trained_at']
    
    def __str__(self):
        return f"{self.name} ({self.n_clusters} clusters)"


class BettorCluster(models.Model):
    """Assigns bettors to clusters with their feature vectors."""
    model = models.ForeignKey(
        ClusteringModel,
        on_delete=models.CASCADE,
        related_name="bettor_clusters"
    )
    bettor_profile = models.ForeignKey(
        BettorProfile,
        on_delete=models.CASCADE,
        related_name="cluster_assignments"
    )
    
    cluster_id = models.PositiveSmallIntegerField()
    confidence = models.FloatField(default=0.0)  # Distance to cluster centroid
    
    # Feature vector used for clustering
    feature_vector = ArrayField(
        models.FloatField(),
        help_text="Feature vector used for this clustering assignment"
    )
    
    assigned_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "bettor_clusters"
        unique_together = [['model', 'bettor_profile']]
        indexes = [
            models.Index(fields=['model', 'cluster_id']),
            models.Index(fields=['bettor_profile', 'model']),
        ]
    
    def __str__(self):
        return f"Bettor {self.bettor_profile.bettor_id} -> Cluster {self.cluster_id}"


class ClusterCharacteristics(models.Model):
    """Analyzes and stores characteristics of each cluster."""
    model = models.ForeignKey(
        ClusteringModel,
        on_delete=models.CASCADE,
        related_name="cluster_characteristics"
    )
    
    cluster_id = models.PositiveSmallIntegerField()
    
    # Cluster centroid (serialized)
    centroid = ArrayField(models.FloatField())
    
    # Statistical summaries
    cluster_size = models.PositiveIntegerField()
    avg_win_rate = models.FloatField()
    avg_roi = models.FloatField()
    avg_bet_amount = models.FloatField()
    avg_strategy_diversity = models.FloatField()
    
    # Behavioral profile
    profile_name = models.CharField(max_length=255, blank=True)
    profile_description = models.TextField(blank=True)
    
    class Meta:
        db_table = "cluster_characteristics"
        unique_together = [['model', 'cluster_id']]
    
    def __str__(self):
        return f"Cluster {self.cluster_id}: {self.profile_name}"


class MLMetrics(models.Model):
    """Track ML model performance over time."""
    model = models.ForeignKey(
        ClusteringModel,
        on_delete=models.CASCADE,
        related_name="metrics"
    )
    
    metric_type = models.CharField(
        max_length=50,
        choices=[
            ('accuracy', 'Accuracy'),
            ('precision', 'Precision'),
            ('recall', 'Recall'),
            ('silhouette', 'Silhouette Score'),
            ('davies_bouldin', 'Davies-Bouldin Index'),
            ('inertia', 'Inertia'),
        ]
    )
    
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "ml_metrics"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.metric_type}: {self.value:.4f}"


class MonteCarloSimulationRun(models.Model):
    """Tracks an offline Monte Carlo bootstrap run for the betting knowledge base."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    random_seed = models.PositiveIntegerField(default=42)
    rounds_simulated = models.PositiveIntegerField(default=0)
    bettors_simulated = models.PositiveIntegerField(default=0)
    characters_per_round = models.PositiveSmallIntegerField(default=5)
    strategies_used = ArrayField(
        models.CharField(max_length=100),
        default=list,
        help_text="Strategy names used in this simulation run",
    )
    average_roi = models.FloatField(default=0.0)
    average_win_rate = models.FloatField(default=0.0)
    total_stake = models.FloatField(default=0.0)
    total_payout = models.FloatField(default=0.0)
    knowledge_base = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monte_carlo_simulation_runs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.rounds_simulated} rounds)"


class MonteCarloStrategyInsight(models.Model):
    """Stores aggregate strategy knowledge generated from a simulation run."""

    simulation_run = models.ForeignKey(
        MonteCarloSimulationRun,
        on_delete=models.CASCADE,
        related_name="strategy_insights",
    )
    strategy_name = models.CharField(max_length=100)
    sample_size = models.PositiveIntegerField(default=0)
    average_roi = models.FloatField(default=0.0)
    average_win_rate = models.FloatField(default=0.0)
    expected_profit = models.FloatField(default=0.0)
    profit_variance = models.FloatField(default=0.0)
    average_stake = models.FloatField(default=0.0)
    top_character_name = models.CharField(max_length=255, blank=True)
    top_character_share = models.FloatField(default=0.0)
    strategy_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monte_carlo_strategy_insights"
        ordering = ["-average_roi", "strategy_name"]
        unique_together = [["simulation_run", "strategy_name"]]

    def __str__(self):
        return f"{self.strategy_name} ({self.average_roi:.2f}% ROI)"


class BetOptionDefinition(models.Model):
    """Catalog of valid virtual-betting option codes (e.g. F3, D1, F2ANDD5)."""

    class BetType(models.TextChoices):
        FLOAT_SINGLE = "float_single", "Float Single"
        DROWN_SINGLE = "drown_single", "Drown Single"
        COMBO = "combo", "Combo"

    option_code = models.CharField(max_length=20, unique=True, db_index=True)
    bet_type = models.CharField(max_length=20, choices=BetType.choices)
    float_phase = models.PositiveSmallIntegerField(null=True, blank=True)
    drown_phase = models.PositiveSmallIntegerField(null=True, blank=True)
    is_combo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bet_option_definitions"
        ordering = ["option_code"]

    def __str__(self):
        return self.option_code


class BetOptionKnowledgeRow(models.Model):
    """Derived dataset row for ML: per character + option_code win probability."""

    version = models.CharField(
        max_length=40,
        default="v1",
        db_index=True,
        help_text="Dataset generator version identifier",
    )
    character = models.ForeignKey(
        "Decision.Character",
        on_delete=models.CASCADE,
        related_name="bet_option_knowledge_rows",
    )
    option = models.ForeignKey(
        BetOptionDefinition,
        on_delete=models.CASCADE,
        related_name="knowledge_rows",
    )
    phase_float_probs = ArrayField(
        models.FloatField(),
        help_text="Per-phase probability of FLOAT given survival (phases 1..5)",
    )
    p_win = models.FloatField(help_text="Probability the option wins")
    implied_fair_odds = models.FloatField(
        null=True,
        blank=True,
        help_text="1 / p_win when p_win > 0",
    )
    metadata = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bet_option_knowledge_rows"
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "character", "option"],
                name="uniq_bet_option_knowledge_version_character_option",
            )
        ]
        indexes = [
            models.Index(fields=["version", "option"]),
            models.Index(fields=["version", "character"]),
        ]

    def __str__(self):
        return f"{self.version} {self.character_id} {self.option.option_code}"


class RoundBettingSnapshot(models.Model):
    """Per-round snapshot of betting population, popularity, and odds signals."""

    round_id = models.PositiveIntegerField(db_index=True)
    game_round_pk = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Decision.GameRound primary key when available",
    )
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    total_pool = models.FloatField(default=0.0)
    total_bets = models.PositiveIntegerField(default=0)

    top_characters = models.JSONField(default=list, blank=True)
    top_phases_live = models.JSONField(default=list, blank=True)
    top_options = models.JSONField(default=list, blank=True)
    top_combos = models.JSONField(default=list, blank=True)
    top_phases_selected = models.JSONField(default=list, blank=True)

    thresholds = models.JSONField(default=dict, blank=True)
    source = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "round_betting_snapshots"
        ordering = ["-captured_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["round_id", "captured_at"],
                name="uniq_round_betting_snapshot_round_captured_at",
            )
        ]

    def __str__(self):
        return f"Round {self.round_id} snapshot @ {self.captured_at.isoformat()}"
