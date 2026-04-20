"""
Serializers for ML-related API endpoints.
"""
from rest_framework import serializers
from .models import (
    BettorProfile, ClusteringModel, BettorCluster,
    ClusterCharacteristics, MLMetrics, BetOptionKnowledgeRow
)


class BettorProfileSerializer(serializers.ModelSerializer):
    """Serializer for BettorProfile."""
    
    class Meta:
        model = BettorProfile
        fields = [
            'id', 'bettor_id', 'total_bets', 'total_wins', 'total_losses',
            'win_rate', 'average_bet_amount', 'max_bet_amount', 'min_bet_amount',
            'bet_variance', 'average_bets_per_round', 'total_active_rounds',
            'favorite_bet_type', 'strategy_diversity', 'total_profit', 'roi',
            'last_updated', 'created_at'
        ]
        read_only_fields = ['id', 'last_updated', 'created_at']


class ClusterCharacteristicsSerializer(serializers.ModelSerializer):
    """Serializer for ClusterCharacteristics."""
    
    class Meta:
        model = ClusterCharacteristics
        fields = [
            'id', 'cluster_id', 'cluster_size', 'avg_win_rate',
            'avg_roi', 'avg_bet_amount', 'avg_strategy_diversity',
            'profile_name', 'profile_description'
        ]
        read_only_fields = fields


class BettorClusterSerializer(serializers.ModelSerializer):
    """Serializer for BettorCluster."""
    
    bettor_profile = BettorProfileSerializer(read_only=True)
    
    class Meta:
        model = BettorCluster
        fields = [
            'id', 'cluster_id', 'confidence', 'assigned_at',
            'last_updated', 'bettor_profile'
        ]
        read_only_fields = fields


class ClusteringModelSerializer(serializers.ModelSerializer):
    """Serializer for ClusteringModel."""
    
    cluster_characteristics = ClusterCharacteristicsSerializer(
        many=True, read_only=True, source='cluster_characteristics'
    )
    
    class Meta:
        model = ClusteringModel
        fields = [
            'id', 'name', 'description', 'n_clusters',
            'num_samples_trained', 'features_used',
            'inertia', 'silhouette_score', 'davies_bouldin_score',
            'is_active', 'trained_at', 'cluster_characteristics'
        ]
        read_only_fields = [
            'id', 'inertia', 'silhouette_score', 'davies_bouldin_score',
            'trained_at', 'cluster_characteristics'
        ]


class ClusterInsightSerializer(serializers.Serializer):
    """Serializer for cluster insights."""
    
    cluster_id = serializers.IntegerField()
    profile_name = serializers.CharField()
    profile_description = serializers.CharField()
    cluster_size = serializers.IntegerField()
    avg_win_rate = serializers.FloatField()
    avg_roi = serializers.FloatField()
    avg_bet_amount = serializers.FloatField()
    avg_strategy_diversity = serializers.FloatField()
    bettor_count = serializers.IntegerField()
    confidence_stats = serializers.DictField()


class MLMetricsSerializer(serializers.ModelSerializer):
    """Serializer for MLMetrics."""
    
    class Meta:
        model = MLMetrics
        fields = ['id', 'metric_type', 'value', 'timestamp']
        read_only_fields = fields


class TrainClusteringModelSerializer(serializers.Serializer):
    """Serializer for training a clustering model."""
    
    model_name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    n_clusters = serializers.IntegerField(min_value=2, max_value=20, default=5)
    random_state = serializers.IntegerField(default=42)
    max_iterations = serializers.IntegerField(default=300)
    n_init = serializers.IntegerField(default=10)


class PredictClusterSerializer(serializers.Serializer):
    """Serializer for predicting a bettor's cluster."""
    
    bettor_id = serializers.CharField(max_length=255)
    cluster_id = serializers.IntegerField(read_only=True)
    confidence = serializers.FloatField(read_only=True)


class BetOptionRecommendationSerializer(serializers.ModelSerializer):
    option_code = serializers.CharField(source="option.option_code", read_only=True)
    bet_type = serializers.CharField(source="option.bet_type", read_only=True)
    float_phase = serializers.IntegerField(source="option.float_phase", read_only=True)
    drown_phase = serializers.IntegerField(source="option.drown_phase", read_only=True)

    class Meta:
        model = BetOptionKnowledgeRow
        fields = [
            "version",
            "character_id",
            "option_code",
            "bet_type",
            "float_phase",
            "drown_phase",
            "p_win",
            "implied_fair_odds",
        ]
        read_only_fields = fields
