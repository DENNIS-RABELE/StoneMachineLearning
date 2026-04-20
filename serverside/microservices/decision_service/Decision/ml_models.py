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
