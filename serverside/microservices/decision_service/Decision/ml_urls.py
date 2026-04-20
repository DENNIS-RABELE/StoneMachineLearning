"""
URL configuration for ML clustering API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from Decision.ml_views import (
    BettorProfileViewSet, ClusteringModelViewSet,
    BettorClusterViewSet, MLMetricsViewSet
)

router = DefaultRouter()
router.register(r'bettor-profiles', BettorProfileViewSet, basename='bettor-profile')
router.register(r'clustering-models', ClusteringModelViewSet, basename='clustering-model')
router.register(r'bettor-clusters', BettorClusterViewSet, basename='bettor-cluster')
router.register(r'ml-metrics', MLMetricsViewSet, basename='ml-metrics')

urlpatterns = [
    path('api/ml/', include(router.urls)),
]
