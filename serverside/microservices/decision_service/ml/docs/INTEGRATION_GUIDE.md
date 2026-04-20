# ML Module Integration Guide

This guide covers setup, configuration, and integration of the ML clustering module with the decision_service.

## Prerequisites

- Python 3.8+
- Django 3.2+
- Pipenv (for dependency management)
- PostgreSQL with ArrayField support

## Installation & Setup

### Step 1: Install Dependencies

Dependencies are defined in the main Pipfile:

```bash
pipenv install scikit-learn numpy pandas scipy matplotlib seaborn joblib
```

Key packages:
- `scikit-learn`: K-means clustering algorithm
- `numpy`, `pandas`: Data processing
- `scipy`: Statistical calculations
- `matplotlib`, `seaborn`: Visualization (optional)
- `joblib`: Model persistence

### Step 2: Run Migrations

Create database tables for ML models:

```bash
cd serverside/microservices/decision_service
python manage.py makemigrations
python manage.py migrate
```

This creates tables:
- `ml_bettorprofile`: Bettor statistics
- `ml_clusteringmodel`: Model metadata
- `ml_bettorcluster`: Cluster assignments
- `ml_clustercharacteristics`: Cluster profiles
- `ml_mlmetrics`: Performance tracking

### Step 3: Register Models in Admin (Optional)

In `Decision/admin.py`:

```python
from Decision.ml.models import (
    BettorProfile, ClusteringModel, BettorCluster, 
    ClusterCharacteristics, MLMetrics
)

admin.site.register(BettorProfile)
admin.site.register(ClusteringModel)
admin.site.register(BettorCluster)
admin.site.register(ClusterCharacteristics)
admin.site.register(MLMetrics)
```

### Step 4: Include URLs in Main Router

In `Decision/urls.py`:

```python
from Decision.ml.urls import api_url_patterns

urlpatterns = [
    path('api/ml/', include(api_url_patterns)),
    # ... other patterns
]
```

Or manually in your router:

```python
from rest_framework.routers import DefaultRouter
from Decision.ml.views import (
    BettorProfileViewSet, ClusteringModelViewSet, 
    BettorClusterViewSet, MLMetricsViewSet
)

router = DefaultRouter()
router.register(r'bettor-profiles', BettorProfileViewSet)
router.register(r'clustering-models', ClusteringModelViewSet)
router.register(r'bettor-clusters', BettorClusterViewSet)
router.register(r'ml-metrics', MLMetricsViewSet)

urlpatterns = router.urls
```

### Step 5: Generate Sample Data (Optional)

For testing with sample bettors:

```bash
python manage.py generate_sample_bettors --count=200 --clear
```

Options:
- `--count=N`: Number of bettors to generate (default: 100)
- `--seed=N`: Random seed for reproducibility (default: 42)
- `--clear`: Delete existing bettors before generating

### Step 6: Train Initial Model

Train your first clustering model:

```bash
python manage.py train_clustering_model \
    --name="v1_initial" \
    --clusters=5 \
    --description="Initial production model"
```

Options:
- `--name`: Model name (required, must be unique)
- `--clusters`: Number of clusters (default: 5)
- `--description`: Model description
- `--random-state`: Random seed (default: 42)
- `--max-iterations`: Max iterations for k-means (default: 300)
- `--n-init`: Number of k-means initializations (default: 10)

## Integration with Existing Components

### Updating Bettor Profiles from Betting History

When new bets are placed, update the bettor profile:

```python
from Decision.ml.models import BettorProfile
from Decision.ml.services.data_preprocessing import BettorDataAggregator

# Get the bettor's betting history (your Bet model)
# This depends on your existing data structure

aggregator = BettorDataAggregator()
aggregator.update_bettor_profile_from_betting_history(
    bettor_id=123,
    betting_history=bets  # List of Bet objects
)
```

### Getting Cluster Predictions

Predict cluster for a bettor:

```python
from Decision.ml.models import ClusteringModel
from Decision.ml.services.kmeans_clustering import KMeansBettorClusterer

# Get active model
model = ClusteringModel.objects.get(is_active=True)

# Create clusterer from saved model
clusterer = KMeansBettorClusterer()
clusterer.load_model(model.model_path)

# Predict cluster
cluster_id = clusterer.predict_cluster(bettor_id=123)
cluster_insights = clusterer.get_cluster_insights(cluster_id)
```

### Using Strategy Recommendations

Get strategy recommendations for a cluster:

```python
from Decision.ml.services.model_analysis import BettorStrategyAnalyzer

analyzer = BettorStrategyAnalyzer()
strategies = analyzer.get_cluster_strategy_profile(cluster_id=2)

# Returns: {
#     'cluster_id': 2,
#     'size': 45,
#     'avg_win_rate': 0.55,
#     'avg_roi': 0.12,
#     'win_rate_recommendation': 'Increase frequency...',
#     'roi_recommendation': 'Focus on consistent...',
#     'strategy_recommendation': 'Develop deeper...'
# }
```

## API Endpoints Reference

### Bettor Profiles
```
GET    /api/ml/bettor-profiles/                    # List all
GET    /api/ml/bettor-profiles/{id}/               # Get one
POST   /api/ml/bettor-profiles/                    # Create
PATCH  /api/ml/bettor-profiles/{id}/               # Partial update
GET    /api/ml/bettor-profiles/update_from_history/ # Batch update
```

Query filters:
- `?min_total_bets=100`
- `?win_rate_min=0.4&win_rate_max=0.6`
- `?roi_min=-0.1&roi_max=0.3`

### Clustering Models
```
GET    /api/ml/clustering-models/                  # List all
GET    /api/ml/clustering-models/{id}/             # Get one
POST   /api/ml/clustering-models/                  # Create
PATCH  /api/ml/clustering-models/{id}/             # Partial update
POST   /api/ml/clustering-models/train_model/      # Train new model
GET    /api/ml/clustering-models/{id}/cluster_summary/  # Summary
GET    /api/ml/clustering-models/{id}/cluster_detail/   # Details
POST   /api/ml/clustering-models/{id}/set_active/  # Set as active
```

### Bettor Clusters
```
GET    /api/ml/bettor-clusters/                    # List assignments
POST   /api/ml/bettor-clusters/predict_cluster/    # Predict for bettor
```

### ML Metrics
```
GET    /api/ml/ml-metrics/                         # List all metrics
```

## Configuration

### Settings

Add to `settings.py` if needed:

```python
# ML Module Configuration
ML_CONFIG = {
    'MIN_BETTORS_FOR_TRAINING': 50,
    'MAX_CLUSTERS': 10,
    'DEFAULT_N_CLUSTERS': 5,
    'MODEL_STORAGE_PATH': 'models/clustering/',
}

# Logging
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'Decision.ml': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
```

## Troubleshooting

### Issue: "No BettorProfile found"
- Generate sample bettors: `python manage.py generate_sample_bettors`
- Or ensure betting history exists and profiles are updated

### Issue: ImportError on ml.models
- Ensure migrations have run: `python manage.py migrate`
- Verify INSTALLED_APPS includes 'Decision' or 'Decision.apps.DecisionConfig'

### Issue: Model training fails with "not enough samples"
- Need at least 50 valid bettors by default
- Generate more sample data or adjust MIN_BETTORS_FOR_TRAINING

### Issue: Clustering results seem poor
- Check Silhouette Score: should be > 0.3
- Try different n_clusters value
- Ensure bettor profiles have enough variation

## Performance Notes

- Training 1000 bettors: ~2-5 seconds
- Predicting single bettor: ~1ms
- Cluster analysis: ~100-500ms depending on cluster size
- Feature extraction: ~10μs per bettor

## Next Steps

1. ✅ Install dependencies
2. ✅ Run migrations
3. ✅ Generate sample data
4. ✅ Train initial model
5. → Integrate with existing betting service
6. → Set up periodic retraining (optional)
7. → Build decision logic based on clusters
8. → Monitor model performance over time
