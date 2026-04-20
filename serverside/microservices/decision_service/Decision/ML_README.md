# Machine Learning Betting Behavior Clustering

This module implements k-means clustering to analyze and group bettor behaviors and strategies within the decision_service. It helps identify bettor archetypes and provides insights for decision-making and strategy recommendations.

## Overview

The ML clustering system analyzes bettor behavior through the following features:

- **Win Rate**: Percentage of successful bets
- **Bet Amount Statistics**: Average, min, max, and variance of bet amounts
- **Betting Frequency**: Number of bets per round and total active rounds
- **Strategy Diversity**: How varied a bettor's betting approaches are
- **ROI (Return on Investment)**: Profit efficiency metric

These features are used to group bettors into clusters representing different behavioral archetypes.

## Architecture

### Models (`ml_models.py`)

1. **BettorProfile**: Aggregated statistics for each bettor
2. **ClusteringModel**: Trained k-means model metadata
3. **BettorCluster**: Assignment of bettors to clusters
4. **ClusterCharacteristics**: Statistical profile of each cluster
5. **MLMetrics**: Performance tracking of models

### Services

#### `kmeans_clustering.py`
Main clustering service with:
- `BettorFeatureExtractor`: Extracts features from profiles
- `KMeansBettorClusterer`: Trains and manages clustering models
- Feature standardization and cluster analysis

#### `data_preprocessing.py`
Data preparation utilities:
- `BettorDataAggregator`: Updates profiles from betting history
- `DataValidationService`: Validates data quality
- `FeatureScalingService`: Normalizes features

#### `model_analysis.py`
Advanced analysis:
- `ModelPersistenceManager`: Save/load models to disk
- `ClusterAnalyzer`: Cluster cohesion and outlier analysis
- `BettorStrategyAnalyzer`: Generate strategy recommendations
- `ModelEvaluationService`: Performance evaluation

### API Views (`ml_views.py`)

RESTful endpoints for:
- `/api/ml/bettor-profiles/`: List and manage bettor profiles
- `/api/ml/clustering-models/`: Train and manage models
- `/api/ml/bettor-clusters/`: View cluster assignments
- `/api/ml/ml-metrics/`: Track model performance

### Management Commands

1. **`generate_sample_bettors`**: Create sample bettor data for testing
   ```bash
   python manage.py generate_sample_bettors --count=100 --seed=42
   ```

2. **`train_clustering_model`**: Train a k-means model
   ```bash
   python manage.py train_clustering_model --name="model_v1" --clusters=5
   ```

## Quick Start

### 1. Setup Database

Add ML models to Django admin and register:

```python
# admin.py - add to existing imports/registrations
from Decision.ml_models import (
    BettorProfile, ClusteringModel, BettorCluster,
    ClusterCharacteristics, MLMetrics
)

admin.site.register(BettorProfile)
admin.site.register(ClusteringModel)
admin.site.register(BettorCluster)
admin.site.register(ClusterCharacteristics)
admin.site.register(MLMetrics)
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Generate Sample Data (Optional)

```bash
python manage.py generate_sample_bettors --count=200 --clear
```

### 4. Train a Model

```bash
python manage.py train_clustering_model \
    --name="production_v1" \
    --clusters=5 \
    --description="Production model trained on 200 bettors"
```

### 5. Use the API

Get all bettor profiles:
```bash
GET /api/ml/bettor-profiles/
```

Get cluster summary:
```bash
GET /api/ml/clustering-models/{id}/cluster_summary/
```

Predict cluster for a bettor:
```bash
POST /api/ml/bettor-clusters/predict_cluster/
{
    "bettor_id": "bettor_000001",
    "model_id": 1
}
```

## Feature Dictionary

| Feature | Description | Range | Type |
|---------|-------------|-------|------|
| `win_rate` | Proportion of successful bets | 0.0 - 1.0 | Float |
| `average_bet_amount` | Mean bet size in currency | 0.0 - ∞ | Float |
| `bet_variance` | Variance in bet amounts | 0.0 - ∞ | Float |
| `average_bets_per_round` | Mean bets placed per round | 0.0 - ∞ | Float |
| `strategy_diversity` | How many different strategies used | 0.0 - 1.0 | Float |
| `roi` | Return on investment percentage | -∞ - ∞ | Float |
| `total_bets` | Lifetime number of bets (normalized) | 0.0 - 1.0 | Float |

## Cluster Insights

Each trained model generates automatic cluster profiles with:

- **Profile Name**: e.g., "Expert Risk-Taker Versatile Bettor"
- **Profile Description**: Natural language summary
- **Average Metrics**: Win rate, ROI, bet size, strategy diversity
- **Cluster Size**: Number of bettors in cluster
- **Confidence Stats**: How well-aligned members are

### Typical Cluster Profiles

1. **Expert Conservative**: High win rate, small bets, focused strategy
2. **Expert Risk-Taker**: High ROI, large bets, diversified strategy
3. **Intermediate Balanced**: Average win rate, moderate bets
4. **Novice Explorers**: Low win rate, low strategy diversity
5. **Aggressive Gamblers**: High variance, large bets, high risk

## Model Training Parameters

```python
KMeansBettorClusterer(
    n_clusters=5,              # Number of clusters (2-20 recommended)
    random_state=42,           # Seed for reproducibility
    max_iterations=300,        # K-means max iterations
    n_init=10                  # Number of initializations
)
```

## Model Evaluation Metrics

1. **Silhouette Score**: -1 to 1 (higher is better, >0.5 is good)
2. **Davies-Bouldin Index**: 0 to ∞ (lower is better)
3. **Inertia**: Sum of squared distances to centroids

## Advanced Usage

### Updating Bettor Profiles

```python
from Decision.services.data_preprocessing import BettorDataAggregator

# Update from betting history
profile = BettorDataAggregator.update_bettor_profile_from_betting_history(
    bettor_id="bettor_123",
    betting_history=[
        {
            'amount': 100,
            'outcome': 'win',
            'payout': 200,
            'round_id': 1,
            'bet_type': 'conservative'
        },
        # ... more bets
    ],
    time_window_days=30  # Last 30 days only
)
```

### Predicting Cluster

```python
from Decision.services.kmeans_clustering import KMeansBettorClusterer
from Decision.ml_models import ClusteringModel, BettorProfile

clusterer = KMeansBettorClusterer()
model = ClusteringModel.objects.get(is_active=True)
profile = BettorProfile.objects.get(bettor_id="bettor_123")

cluster_id, confidence = clusterer.predict_cluster(profile, model)
print(f"Cluster: {cluster_id}, Confidence: {confidence:.2%}")
```

### Analyzing Clusters

```python
from Decision.services.model_analysis import ClusterAnalyzer, BettorStrategyAnalyzer

# Cohesion analysis
cohesion = ClusterAnalyzer.analyze_cluster_cohesion(model)

# Find outliers
outliers = ClusterAnalyzer.find_cluster_outliers(model, cluster_id=0, percentile=10)

# Strategy profile
strategy = BettorStrategyAnalyzer.get_cluster_strategy_profile(model, cluster_id=0)
```

## Performance Considerations

- **Training Time**: Increases with number of bettors and features
- **Memory**: Stores full feature matrix during training
- **Inference**: Prediction is very fast (~1ms per bettor)
- **Scalability**: Can handle 10,000+ bettors efficiently

## Error Handling

Common errors and solutions:

1. **"Need at least X bettors"**: Generate more sample data
2. **"No active clustering model"**: Set a model as active via API
3. **"Invalid bettor profile"**: Check win_rate is 0-1, no NaN values

## Integration Points

The ML module integrates with:
- Django ORM for data persistence
- Django REST Framework for API
- Celery for async training (optional)
- Redis for caching model metadata (optional)

## Future Enhancements

- [ ] Hierarchical clustering for nested profiles
- [ ] Online learning to update clusters incrementally
- [ ] Anomaly detection for suspicious betting patterns
- [ ] Visualization dashboard with cluster insights
- [ ] Recommendation system based on cluster strategies
- [ ] Feature engineering pipeline
- [ ] Model versioning and A/B testing

## References

- [Scikit-learn K-means](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)
- [Silhouette Coefficient](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html)
- [Davies-Bouldin Index](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html)
