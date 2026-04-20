# ML Module Integration Guide

This guide explains how to integrate the new ML clustering module into the existing decision_service project.

## Step 1: Update settings.py

Add ML models to INSTALLED_APPS (if using a separate ml app):

```python
# decision_service/settings.py

INSTALLED_APPS = [
    # ... existing apps
    'Decision',  # Existing app - ML models are added here
]
```

No additional changes needed as the ML models are added to the existing Decision app.

## Step 2: Update Admin Registration

Add ML models to Django admin:

```python
# Decision/admin.py

from django.contrib import admin
from Decision.models import (
    GameRound, DecisionRound, Phase, Bet_decision,
    Character, Outcome
)
from Decision.ml_models import (
    BettorProfile, ClusteringModel, BettorCluster,
    ClusterCharacteristics, MLMetrics
)

# ... existing admin registrations

@admin.register(BettorProfile)
class BettorProfileAdmin(admin.ModelAdmin):
    list_display = ['bettor_id', 'total_bets', 'win_rate', 'roi', 'last_updated']
    search_fields = ['bettor_id']
    list_filter = ['last_updated', 'win_rate']
    readonly_fields = ['created_at', 'last_updated']


@admin.register(ClusteringModel)
class ClusteringModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'n_clusters', 'is_active', 'silhouette_score', 'trained_at']
    search_fields = ['name']
    list_filter = ['is_active', 'trained_at', 'n_clusters']
    readonly_fields = ['inertia', 'silhouette_score', 'davies_bouldin_score', 'trained_at']
    
    fieldsets = (
        ('Model Info', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Configuration', {
            'fields': ('n_clusters', 'random_state', 'max_iterations', 'n_init')
        }),
        ('Performance', {
            'fields': ('silhouette_score', 'davies_bouldin_score', 'inertia')
        }),
        ('Metadata', {
            'fields': ('num_samples_trained', 'features_used', 'trained_at')
        }),
    )


@admin.register(BettorCluster)
class BettorClusterAdmin(admin.ModelAdmin):
    list_display = ['bettor_profile', 'cluster_id', 'confidence', 'assigned_at']
    search_fields = ['bettor_profile__bettor_id']
    list_filter = ['model', 'cluster_id', 'assigned_at']
    readonly_fields = ['assigned_at', 'last_updated']


@admin.register(ClusterCharacteristics)
class ClusterCharacteristicsAdmin(admin.ModelAdmin):
    list_display = ['model', 'cluster_id', 'profile_name', 'cluster_size', 'avg_roi']
    search_fields = ['profile_name', 'model__name']
    list_filter = ['model', 'cluster_id']
    readonly_fields = ['centroid']


@admin.register(MLMetrics)
class MLMetricsAdmin(admin.ModelAdmin):
    list_display = ['model', 'metric_type', 'value', 'timestamp']
    search_fields = ['model__name']
    list_filter = ['model', 'metric_type', 'timestamp']
    readonly_fields = ['timestamp']
```

## Step 3: Update Main URLs

Include ML URLs in the main urls.py:

```python
# decision_service/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # ... existing paths
    
    # ML Module URLs
    path('', include('Decision.ml_urls')),
]
```

Alternatively, if using API versioning:

```python
# decision_service/urls.py

urlpatterns = [
    # ... existing paths
    path('api/v1/', include('Decision.ml_urls')),
]
```

## Step 4: Run Migrations

Create and run migrations:

```bash
# Create migration file
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

## Step 5: Install ML Dependencies

Update Pipfile with ML packages (already done):

```bash
# Install dependencies
pipenv install

# Or if using pip
pip install scikit-learn numpy pandas scipy matplotlib seaborn joblib
```

## Step 6: Setup Celery Tasks (Optional)

For async model training with Celery:

```python
# Decision/tasks.py

from celery import shared_task
from Decision.services.kmeans_clustering import KMeansBettorClusterer
import logging

logger = logging.getLogger(__name__)

@shared_task
def train_clustering_model_async(model_name, n_clusters=5, **kwargs):
    """Async task to train clustering model."""
    try:
        clusterer = KMeansBettorClusterer(n_clusters=n_clusters)
        model = clusterer.train(model_name=model_name, **kwargs)
        logger.info(f"Model {model_name} trained successfully")
        return {
            'status': 'success',
            'model_id': model.id,
            'model_name': model.name
        }
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }
```

## Step 7: Configure Logging

Add logging configuration:

```python
# decision_service/settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'ml_module.log',
        },
    },
    'loggers': {
        'Decision': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
```

## Step 8: Create Cache Configuration (Optional)

For caching model metadata:

```python
# decision_service/settings.py

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache active clustering model for 1 hour
ML_MODEL_CACHE_TIMEOUT = 3600
```

## Step 9: Verification Steps

1. **Check migrations**:
   ```bash
   python manage.py showmigrations Decision
   ```

2. **Verify admin registration**:
   ```bash
   python manage.py check
   ```

3. **Test imports**:
   ```bash
   python manage.py shell
   >>> from Decision.ml_models import BettorProfile
   >>> from Decision.services.kmeans_clustering import KMeansBettorClusterer
   >>> print("ML module imported successfully!")
   ```

4. **Generate sample data**:
   ```bash
   python manage.py generate_sample_bettors --count=50
   ```

5. **Train a test model**:
   ```bash
   python manage.py train_clustering_model --name="test" --clusters=3
   ```

6. **Test API**:
   ```bash
   curl http://localhost:8000/api/ml/bettor-profiles/ \
       -H "Authorization: Bearer YOUR_TOKEN"
   ```

## Step 10: Permissions (Optional)

Set up API permissions:

```python
# Decision/permissions.py

from rest_framework import permissions

class IsMLAdmin(permissions.BasePermission):
    """Only allow ML admins to train models."""
    
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='ml_admins').exists()


class CanViewClusters(permissions.BasePermission):
    """Allow viewing clusters for authenticated users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
```

Apply to views:

```python
# Decision/ml_views.py

from Decision.permissions import IsMLAdmin, CanViewClusters

class ClusteringModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsMLAdmin]  # Only admins can train
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'cluster_summary']:
            return [CanViewClusters()]
        return [IsMLAdmin()]
```

## File Structure After Integration

```
decision_service/
├── decision_service/
│   ├── settings.py          # Updated: Added logging
│   ├── urls.py              # Updated: Added ml_urls include
│   └── wsgi.py
├── Decision/
│   ├── admin.py             # Updated: Added ML model registration
│   ├── models.py            # Existing models
│   ├── ml_models.py         # NEW: ML data models
│   ├── ml_serializers.py    # NEW: REST serializers
│   ├── ml_views.py          # NEW: REST views
│   ├── ml_urls.py           # NEW: URL routing
│   ├── ML_README.md         # NEW: Documentation
│   ├── ML_EXAMPLES.py       # NEW: Usage examples
│   ├── ML_IMPLEMENTATION_SUMMARY.md  # NEW: Summary
│   ├── services/
│   │   ├── kmeans_clustering.py       # NEW: ML engine
│   │   ├── data_preprocessing.py      # NEW: Data prep
│   │   └── model_analysis.py          # NEW: Analysis
│   ├── management/commands/
│   │   ├── train_clustering_model.py  # NEW: Train CLI
│   │   └── generate_sample_bettors.py # NEW: Sample data
│   ├── migrations/
│   │   └── XXXX_ml_models.py          # NEW: ML schema
│   └── ...existing files...
├── Pipfile                  # Updated: Added ML deps
└── manage.py
```

## Troubleshooting

### Issue: "No module named 'sklearn'"
```bash
pipenv install scikit-learn
# or
pip install scikit-learn
```

### Issue: "Migration conflicts"
```bash
python manage.py migrate --fake Decision zero
python manage.py migrate Decision
```

### Issue: "Module 'Decision' has no attribute 'ml_models'"
- Ensure `ml_models.py` is in the Decision directory
- Verify `__init__.py` exists in Decision/services/

### Issue: "API endpoints not found"
- Check `ml_urls.py` is included in main urls.py
- Verify routing: `python manage.py show_urls | grep ml`

## Performance Tuning

### For Large Datasets (>10,000 bettors)
```python
# Use mini-batch k-means
from sklearn.cluster import MiniBatchKMeans

# Modify kmeans_clustering.py
self.kmeans = MiniBatchKMeans(
    n_clusters=self.n_clusters,
    batch_size=100,
    random_state=self.random_state
)
```

### Enable Caching
```python
# ml_views.py
from django.views.decorators.cache import cache_page

@cache_page(3600)  # Cache for 1 hour
def cluster_summary(self, request, pk=None):
    ...
```

### Database Optimization
```python
# Add indexes in admin
class BettorProfileAdmin(admin.ModelAdmin):
    list_select_related = ['related_profiles']
```

## Production Deployment

1. **Set DEBUG = False** in settings.py
2. **Configure static files** for admin interface
3. **Set up SSL/TLS** for API endpoints
4. **Configure CORS** if frontend is separate
5. **Set up monitoring** for ML model performance
6. **Configure backups** for model persistence files
7. **Set up rate limiting** for training endpoints

## Security Considerations

1. Add authentication to all ML endpoints
2. Limit training endpoint to admins only
3. Validate input data thoroughly
4. Sanitize bettor IDs and data
5. Set up audit logging for model changes
6. Implement role-based access control

---

**Ready to use!** Your decision_service now has a fully integrated ML clustering module.
