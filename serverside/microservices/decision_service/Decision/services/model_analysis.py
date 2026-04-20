"""
Model persistence, serialization and advanced analysis utilities.
"""
import json
import pickle
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import os

from Decision.ml_models import ClusteringModel, MLMetrics
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class ModelPersistenceManager:
    """Handles saving and loading ML models from disk."""
    
    MODEL_SAVE_DIR = 'ml_models'
    
    @classmethod
    def get_model_path(cls, model_id: int) -> str:
        """Get file path for a model."""
        os.makedirs(cls.MODEL_SAVE_DIR, exist_ok=True)
        return os.path.join(cls.MODEL_SAVE_DIR, f'model_{model_id}.pkl')
    
    @classmethod
    def save_model(cls, clustering_model: ClusteringModel, 
                  kmeans: KMeans, scaler: StandardScaler) -> str:
        """
        Save a trained k-means model and scaler to disk.
        
        Args:
            clustering_model: ClusteringModel instance (DB record)
            kmeans: Trained KMeans instance
            scaler: Trained StandardScaler instance
            
        Returns:
            Path to saved model
        """
        model_path = cls.get_model_path(clustering_model.id)
        
        model_data = {
            'model_id': clustering_model.id,
            'kmeans': kmeans,
            'scaler': scaler,
            'timestamp': datetime.now().isoformat(),
            'features_used': clustering_model.features_used,
        }
        
        try:
            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info(f"Model saved to {model_path}")
            return model_path
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            raise
    
    @classmethod
    def load_model(cls, clustering_model: ClusteringModel) -> tuple:
        """
        Load a saved k-means model and scaler from disk.
        
        Args:
            clustering_model: ClusteringModel instance
            
        Returns:
            Tuple of (kmeans, scaler)
        """
        model_path = cls.get_model_path(clustering_model.id)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")
        
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            logger.info(f"Model loaded from {model_path}")
            return model_data['kmeans'], model_data['scaler']
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise
    
    @classmethod
    def delete_model(cls, model_id: int) -> None:
        """Delete saved model file."""
        model_path = cls.get_model_path(model_id)
        try:
            if os.path.exists(model_path):
                os.remove(model_path)
                logger.info(f"Model deleted: {model_path}")
        except Exception as e:
            logger.error(f"Error deleting model: {str(e)}")
            raise


class ClusterAnalyzer:
    """Advanced analysis of clusters and bettor patterns."""
    
    @staticmethod
    def analyze_cluster_cohesion(clustering_model: ClusteringModel) -> Dict[int, float]:
        """
        Analyze how cohesive each cluster is.
        
        Returns:
            Dict mapping cluster_id to cohesion score (0-1, higher is better)
        """
        from Decision.ml_models import BettorCluster
        
        cohesion_scores = {}
        
        for cluster_id in range(clustering_model.n_clusters):
            assignments = BettorCluster.objects.filter(
                model=clustering_model,
                cluster_id=cluster_id
            )
            
            if not assignments.exists():
                cohesion_scores[cluster_id] = 0.0
                continue
            
            # Average confidence is a proxy for cohesion
            avg_confidence = np.mean([a.confidence for a in assignments])
            cohesion_scores[cluster_id] = avg_confidence
        
        return cohesion_scores
    
    @staticmethod
    def find_cluster_outliers(clustering_model: ClusteringModel,
                             cluster_id: int,
                             percentile: int = 10) -> List[str]:
        """
        Find outliers (low confidence bettors) in a cluster.
        
        Args:
            clustering_model: ClusteringModel instance
            cluster_id: Cluster ID
            percentile: Lowest percentile to consider as outliers
            
        Returns:
            List of bettor_ids
        """
        from Decision.ml_models import BettorCluster
        
        assignments = list(BettorCluster.objects.filter(
            model=clustering_model,
            cluster_id=cluster_id
        ).select_related('bettor_profile'))
        
        if not assignments:
            return []
        
        confidences = [a.confidence for a in assignments]
        threshold = np.percentile(confidences, percentile)
        
        outliers = [
            a.bettor_profile.bettor_id
            for a in assignments
            if a.confidence <= threshold
        ]
        
        return outliers
    
    @staticmethod
    def compare_models(model1_id: int, model2_id: int) -> Dict[str, Any]:
        """
        Compare two clustering models.
        
        Returns:
            Comparison metrics
        """
        model1 = ClusteringModel.objects.get(id=model1_id)
        model2 = ClusteringModel.objects.get(id=model2_id)
        
        return {
            'model1': {
                'name': model1.name,
                'silhouette': model1.silhouette_score,
                'davies_bouldin': model1.davies_bouldin_score,
                'inertia': model1.inertia,
                'n_clusters': model1.n_clusters,
            },
            'model2': {
                'name': model2.name,
                'silhouette': model2.silhouette_score,
                'davies_bouldin': model2.davies_bouldin_score,
                'inertia': model2.inertia,
                'n_clusters': model2.n_clusters,
            },
            'better_model': 'model1' if model1.silhouette_score > model2.silhouette_score else 'model2',
        }
    
    @staticmethod
    def analyze_cluster_transitions(
        old_model_id: int,
        new_model_id: int
    ) -> Dict[str, Any]:
        """
        Analyze how bettors moved between clusters when models changed.
        
        Returns:
            Transition analysis
        """
        from Decision.ml_models import BettorCluster
        
        old_assignments = BettorCluster.objects.filter(
            model_id=old_model_id
        ).select_related('bettor_profile')
        
        new_assignments = BettorCluster.objects.filter(
            model_id=new_model_id
        ).select_related('bettor_profile')
        
        old_dict = {a.bettor_profile.bettor_id: a.cluster_id 
                   for a in old_assignments}
        new_dict = {a.bettor_profile.bettor_id: a.cluster_id 
                   for a in new_assignments}
        
        # Find common bettors
        common_bettors = set(old_dict.keys()) & set(new_dict.keys())
        
        # Count transitions
        transitions = {}
        for bettor_id in common_bettors:
            old_cluster = old_dict[bettor_id]
            new_cluster = new_dict[bettor_id]
            
            key = f"cluster_{old_cluster}_to_{new_cluster}"
            transitions[key] = transitions.get(key, 0) + 1
        
        return {
            'total_bettors_compared': len(common_bettors),
            'bettors_changed_clusters': sum(
                1 for bid in common_bettors
                if old_dict[bid] != new_dict[bid]
            ),
            'cluster_transitions': transitions,
        }


class BettorStrategyAnalyzer:
    """Analyze betting strategies by cluster."""
    
    @staticmethod
    def get_cluster_strategy_profile(clustering_model, cluster_id: int) -> Dict:
        """
        Generate a detailed strategy profile for a cluster.
        
        Returns:
            Strategy profile with actionable insights
        """
        from Decision.ml_models import BettorCluster, ClusterCharacteristics
        
        characteristics = ClusterCharacteristics.objects.get(
            model=clustering_model,
            cluster_id=cluster_id
        )
        
        assignments = list(BettorCluster.objects.filter(
            model=clustering_model,
            cluster_id=cluster_id
        ).select_related('bettor_profile'))
        
        # Calculate strategy metrics
        profiles = [a.bettor_profile for a in assignments]
        bet_amounts = [p.average_bet_amount for p in profiles]
        win_rates = [p.win_rate for p in profiles]
        rois = [p.roi for p in profiles]
        
        return {
            'cluster_id': cluster_id,
            'profile_name': characteristics.profile_name,
            'profile_description': characteristics.profile_description,
            'strategy_recommendations': BettorStrategyAnalyzer._generate_recommendations(
                characteristics, profiles
            ),
            'metrics': {
                'avg_win_rate': float(np.mean(win_rates)),
                'median_win_rate': float(np.median(win_rates)),
                'std_win_rate': float(np.std(win_rates)),
                'avg_roi': float(np.mean(rois)),
                'median_roi': float(np.median(rois)),
                'avg_bet_size': float(np.mean(bet_amounts)),
                'median_bet_size': float(np.median(bet_amounts)),
            },
            'member_count': len(assignments),
        }
    
    @staticmethod
    def _generate_recommendations(characteristics, profiles: List) -> List[str]:
        """Generate strategy recommendations based on cluster characteristics."""
        recommendations = []
        
        # Analyze win rate
        win_rates = [p.win_rate for p in profiles]
        avg_win_rate = np.mean(win_rates)
        
        if avg_win_rate < 0.45:
            recommendations.append(
                "Consider more conservative betting to improve overall win rate"
            )
        elif avg_win_rate > 0.55:
            recommendations.append(
                "Strong win rate - continue current strategy with potential to increase bet sizes"
            )
        
        # Analyze ROI
        avg_roi = characteristics.avg_roi
        
        if avg_roi < 0:
            recommendations.append(
                "Negative ROI - review bet selection criteria and risk management"
            )
        elif avg_roi > 20:
            recommendations.append(
                "Excellent ROI - consider sharing successful strategies with others"
            )
        
        # Analyze diversity
        if characteristics.avg_strategy_diversity < 0.3:
            recommendations.append(
                "Low strategy diversity - consider exploring different bet types"
            )
        
        return recommendations


class ModelEvaluationService:
    """Service for evaluating and comparing model performance."""
    
    @staticmethod
    def evaluate_model_stability(clustering_model: ClusteringModel,
                                 time_period_days: int = 7) -> Dict[str, float]:
        """
        Evaluate how stable a model's predictions are over time.
        
        Args:
            clustering_model: ClusteringModel to evaluate
            time_period_days: Days to look back
            
        Returns:
            Stability metrics
        """
        from Decision.ml_models import BettorCluster
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=time_period_days)
        
        recent_assignments = BettorCluster.objects.filter(
            model=clustering_model,
            last_updated__gte=cutoff_date
        )
        
        # Measure variance in cluster sizes
        cluster_sizes = {}
        for assignment in recent_assignments:
            cid = assignment.cluster_id
            cluster_sizes[cid] = cluster_sizes.get(cid, 0) + 1
        
        if not cluster_sizes:
            return {'stability_score': 0.0}
        
        # Lower variance in cluster sizes = more stable
        size_variance = np.var(list(cluster_sizes.values()))
        max_variance = len(cluster_sizes) * 1000  # Normalize
        stability = max(0, 1 - (size_variance / max_variance))
        
        return {
            'stability_score': float(stability),
            'cluster_sizes': cluster_sizes,
            'evaluation_period_days': time_period_days,
        }
    
    @staticmethod
    def get_model_performance_report(clustering_model: ClusteringModel) -> Dict:
        """Generate comprehensive performance report for a model."""
        from Decision.ml_models import BettorCluster, ClusterCharacteristics
        
        report = {
            'model_id': clustering_model.id,
            'model_name': clustering_model.name,
            'trained_at': clustering_model.trained_at.isoformat(),
            'quality_metrics': {
                'silhouette_score': clustering_model.silhouette_score,
                'davies_bouldin_score': clustering_model.davies_bouldin_score,
                'inertia': clustering_model.inertia,
            },
            'data_metrics': {
                'num_samples': clustering_model.num_samples_trained,
                'num_clusters': clustering_model.n_clusters,
                'features_used': clustering_model.features_used,
            },
            'cluster_distribution': {},
        }
        
        # Get distribution
        for cluster_id in range(clustering_model.n_clusters):
            count = BettorCluster.objects.filter(
                model=clustering_model,
                cluster_id=cluster_id
            ).count()
            report['cluster_distribution'][f'cluster_{cluster_id}'] = count
        
        return report
