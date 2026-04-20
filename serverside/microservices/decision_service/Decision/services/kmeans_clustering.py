"""
K-means clustering service for analyzing betting behavior and strategies.
"""
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score
from django.utils import timezone
from typing import Dict, List, Tuple, Optional
import logging

from Decision.ml_models import (
    BettorProfile, ClusteringModel, BettorCluster, 
    ClusterCharacteristics, MLMetrics
)

logger = logging.getLogger(__name__)


class BettorFeatureExtractor:
    """Extracts features from bettor profiles for clustering."""
    
    # Define the features to use for clustering
    FEATURE_NAMES = [
        'win_rate',
        'average_bet_amount',
        'bet_variance',
        'average_bets_per_round',
        'strategy_diversity',
        'roi',
        'total_bets',  # normalized later
    ]
    
    @staticmethod
    def extract_features(bettor_profile: BettorProfile) -> np.ndarray:
        """
        Extract feature vector from a bettor profile.
        
        Args:
            bettor_profile: BettorProfile instance
            
        Returns:
            Feature vector as numpy array
        """
        features = np.array([
            bettor_profile.win_rate,
            bettor_profile.average_bet_amount,
            bettor_profile.bet_variance,
            bettor_profile.average_bets_per_round,
            bettor_profile.strategy_diversity,
            bettor_profile.roi,
            min(bettor_profile.total_bets, 10000) / 10000,  # normalize
        ], dtype=np.float32)
        
        return features
    
    @staticmethod
    def extract_features_batch(bettor_profiles: List[BettorProfile]) -> np.ndarray:
        """
        Extract feature matrix from multiple bettor profiles.
        
        Args:
            bettor_profiles: List of BettorProfile instances
            
        Returns:
            Feature matrix (n_samples, n_features)
        """
        features = np.array([
            BettorFeatureExtractor.extract_features(profile)
            for profile in bettor_profiles
        ], dtype=np.float32)
        
        return features


class KMeansBettorClusterer:
    """Main service for k-means clustering of bettor behavior."""
    
    def __init__(self, n_clusters: int = 5, random_state: int = 42, 
                 max_iterations: int = 300, n_init: int = 10):
        """
        Initialize the clustering service.
        
        Args:
            n_clusters: Number of clusters
            random_state: Random seed for reproducibility
            max_iterations: Maximum iterations for k-means
            n_init: Number of initializations
        """
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.max_iterations = max_iterations
        self.n_init = n_init
        self.scaler = StandardScaler()
        self.kmeans = None
        self.feature_extractor = BettorFeatureExtractor()
    
    def train(self, model_name: str, description: str = "") -> ClusteringModel:
        """
        Train a k-means clustering model on all bettors.
        
        Args:
            model_name: Name for the model
            description: Optional description
            
        Returns:
            ClusteringModel instance
            
        Raises:
            ValueError: If there are insufficient bettors to train
        """
        # Get all bettor profiles
        bettor_profiles = list(BettorProfile.objects.all())
        
        if len(bettor_profiles) < self.n_clusters:
            raise ValueError(
                f"Need at least {self.n_clusters} bettors to train, "
                f"but only {len(bettor_profiles)} available"
            )
        
        logger.info(f"Training k-means model with {len(bettor_profiles)} bettors")
        
        # Extract features
        X = self.feature_extractor.extract_features_batch(bettor_profiles)
        
        # Standardize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train k-means
        self.kmeans = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            max_iter=self.max_iterations,
            n_init=self.n_init,
            verbose=0
        )
        labels = self.kmeans.fit_predict(X_scaled)
        
        # Calculate metrics
        silhouette = silhouette_score(X_scaled, labels)
        davies_bouldin = davies_bouldin_score(X_scaled, labels)
        inertia = self.kmeans.inertia_
        
        logger.info(
            f"Model trained - Silhouette: {silhouette:.4f}, "
            f"Davies-Bouldin: {davies_bouldin:.4f}, "
            f"Inertia: {inertia:.4f}"
        )
        
        # Save model to database
        clustering_model = ClusteringModel.objects.create(
            name=model_name,
            description=description,
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            max_iterations=self.max_iterations,
            n_init=self.n_init,
            num_samples_trained=len(bettor_profiles),
            features_used=self.feature_extractor.FEATURE_NAMES,
            inertia=float(inertia),
            silhouette_score=float(silhouette),
            davies_bouldin_score=float(davies_bouldin),
            model_params={
                'scaler_mean': self.scaler.mean_.tolist(),
                'scaler_scale': self.scaler.scale_.tolist(),
                'centroids': self.kmeans.cluster_centers_.tolist(),
            }
        )
        
        # Save cluster assignments
        self._save_cluster_assignments(clustering_model, bettor_profiles, X_scaled, labels)
        
        # Analyze and save cluster characteristics
        self._analyze_clusters(clustering_model, bettor_profiles, labels)
        
        logger.info(f"Model '{model_name}' trained and saved successfully")
        return clustering_model
    
    def _save_cluster_assignments(self, clustering_model: ClusteringModel,
                                  bettor_profiles: List[BettorProfile],
                                  X_scaled: np.ndarray, labels: np.ndarray) -> None:
        """Save bettor-to-cluster assignments."""
        for bettor_profile, label, features_scaled in zip(
            bettor_profiles, labels, X_scaled
        ):
            # Calculate distance to centroid (as confidence metric)
            centroid = self.kmeans.cluster_centers_[label]
            distance = np.linalg.norm(features_scaled - centroid)
            confidence = 1.0 / (1.0 + distance)  # Convert to 0-1 range
            
            BettorCluster.objects.update_or_create(
                model=clustering_model,
                bettor_profile=bettor_profile,
                defaults={
                    'cluster_id': int(label),
                    'confidence': float(confidence),
                    'feature_vector': self.feature_extractor.extract_features(
                        bettor_profile
                    ).tolist(),
                }
            )
    
    def _analyze_clusters(self, clustering_model: ClusteringModel,
                          bettor_profiles: List[BettorProfile],
                          labels: np.ndarray) -> None:
        """Analyze characteristics of each cluster."""
        cluster_assignments = list(zip(bettor_profiles, labels))
        
        for cluster_id in range(self.n_clusters):
            # Get bettors in this cluster
            cluster_bettors = [
                profile for profile, label in cluster_assignments
                if label == cluster_id
            ]
            
            if not cluster_bettors:
                continue
            
            # Calculate cluster statistics
            win_rates = [p.win_rate for p in cluster_bettors]
            rois = [p.roi for p in cluster_bettors]
            bet_amounts = [p.average_bet_amount for p in cluster_bettors]
            diversities = [p.strategy_diversity for p in cluster_bettors]
            
            avg_win_rate = np.mean(win_rates)
            avg_roi = np.mean(rois)
            avg_bet_amount = np.mean(bet_amounts)
            avg_diversity = np.mean(diversities)
            
            # Generate profile name and description
            profile_name = self._generate_cluster_name(
                avg_win_rate, avg_roi, avg_bet_amount, avg_diversity
            )
            profile_description = self._generate_cluster_description(
                cluster_id, len(cluster_bettors), avg_win_rate, avg_roi, avg_diversity
            )
            
            ClusterCharacteristics.objects.update_or_create(
                model=clustering_model,
                cluster_id=cluster_id,
                defaults={
                    'centroid': self.kmeans.cluster_centers_[cluster_id].tolist(),
                    'cluster_size': len(cluster_bettors),
                    'avg_win_rate': float(avg_win_rate),
                    'avg_roi': float(avg_roi),
                    'avg_bet_amount': float(avg_bet_amount),
                    'avg_strategy_diversity': float(avg_diversity),
                    'profile_name': profile_name,
                    'profile_description': profile_description,
                }
            )
    
    @staticmethod
    def _generate_cluster_name(win_rate: float, roi: float, 
                              bet_amount: float, diversity: float) -> str:
        """Generate a descriptive name for a cluster."""
        performance = "Expert" if win_rate > 0.55 else "Intermediate" if win_rate > 0.45 else "Novice"
        risk = "Risk-Taker" if bet_amount > 100 else "Conservative" if bet_amount < 50 else "Moderate"
        strategy = "Versatile" if diversity > 0.6 else "Focused" if diversity < 0.3 else "Balanced"
        
        return f"{performance} {risk} {strategy} Bettor"
    
    @staticmethod
    def _generate_cluster_description(cluster_id: int, size: int, 
                                     win_rate: float, roi: float, 
                                     diversity: float) -> str:
        """Generate a description of cluster characteristics."""
        return (
            f"Cluster {cluster_id} contains {size} bettors with "
            f"{win_rate:.1%} average win rate, {roi:.2%} ROI, "
            f"and {diversity:.1%} strategy diversity."
        )
    
    def predict_cluster(self, bettor_profile: BettorProfile, 
                       clustering_model: ClusteringModel) -> Tuple[int, float]:
        """
        Predict which cluster a bettor belongs to.
        
        Args:
            bettor_profile: BettorProfile instance
            clustering_model: ClusteringModel to use for prediction
            
        Returns:
            Tuple of (cluster_id, confidence)
        """
        if not self.kmeans:
            # Load model from database
            self._load_model(clustering_model)
        
        # Extract features
        features = self.feature_extractor.extract_features(bettor_profile)
        features_scaled = self.scaler.transform([features])[0]
        
        # Predict cluster
        cluster_id = self.kmeans.predict([features_scaled])[0]
        
        # Calculate confidence
        centroid = self.kmeans.cluster_centers_[cluster_id]
        distance = np.linalg.norm(features_scaled - centroid)
        confidence = 1.0 / (1.0 + distance)
        
        return int(cluster_id), float(confidence)
    
    def _load_model(self, clustering_model: ClusteringModel) -> None:
        """Load model parameters from database."""
        params = clustering_model.model_params
        
        # Restore scaler
        self.scaler.mean_ = np.array(params['scaler_mean'])
        self.scaler.scale_ = np.array(params['scaler_scale'])
        
        # Restore k-means
        self.kmeans = KMeans(
            n_clusters=clustering_model.n_clusters,
            random_state=clustering_model.random_state,
            max_iter=clustering_model.max_iterations,
            n_init=1,
        )
        self.kmeans.cluster_centers_ = np.array(params['centroids'])
    
    def get_cluster_insights(self, clustering_model: ClusteringModel,
                            cluster_id: int) -> Dict:
        """
        Get insights about a specific cluster.
        
        Args:
            clustering_model: ClusteringModel instance
            cluster_id: Cluster ID
            
        Returns:
            Dictionary with cluster insights
        """
        characteristics = ClusterCharacteristics.objects.get(
            model=clustering_model,
            cluster_id=cluster_id
        )
        
        bettors = BettorCluster.objects.filter(
            model=clustering_model,
            cluster_id=cluster_id
        ).select_related('bettor_profile')
        
        return {
            'cluster_id': cluster_id,
            'profile_name': characteristics.profile_name,
            'profile_description': characteristics.profile_description,
            'cluster_size': characteristics.cluster_size,
            'avg_win_rate': characteristics.avg_win_rate,
            'avg_roi': characteristics.avg_roi,
            'avg_bet_amount': characteristics.avg_bet_amount,
            'avg_strategy_diversity': characteristics.avg_strategy_diversity,
            'bettor_count': bettors.count(),
            'confidence_stats': {
                'avg_confidence': float(np.mean([bc.confidence for bc in bettors])),
                'min_confidence': float(np.min([bc.confidence for bc in bettors])),
                'max_confidence': float(np.max([bc.confidence for bc in bettors])),
            }
        }
    
    def get_all_clusters_summary(self, clustering_model: ClusteringModel) -> Dict:
        """Get summary of all clusters in a model."""
        summaries = []
        for cluster_id in range(self.n_clusters):
            try:
                summary = self.get_cluster_insights(clustering_model, cluster_id)
                summaries.append(summary)
            except ClusterCharacteristics.DoesNotExist:
                logger.warning(f"Characteristics not found for cluster {cluster_id}")
                continue
        
        return {
            'model_name': clustering_model.name,
            'n_clusters': clustering_model.n_clusters,
            'silhouette_score': clustering_model.silhouette_score,
            'davies_bouldin_score': clustering_model.davies_bouldin_score,
            'inertia': clustering_model.inertia,
            'num_samples_trained': clustering_model.num_samples_trained,
            'trained_at': clustering_model.trained_at.isoformat(),
            'clusters': summaries,
        }
