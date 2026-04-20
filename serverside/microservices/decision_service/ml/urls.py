"""
URL configuration for ML clustering API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BettorProfileViewSet,
    ClusteringModelViewSet,
    BettorClusterViewSet,
    MLMetricsViewSet,
    BetOptionKnowledgeViewSet,
    dashboard_view,
    dashboard_data_view,
)

router = DefaultRouter()
router.register(r'bettor-profiles', BettorProfileViewSet, basename='bettor-profile')
router.register(r'clustering-models', ClusteringModelViewSet, basename='clustering-model')
router.register(r'bettor-clusters', BettorClusterViewSet, basename='bettor-cluster')
router.register(r'ml-metrics', MLMetricsViewSet, basename='ml-metrics')
router.register(r'bet-option-knowledge', BetOptionKnowledgeViewSet, basename='bet-option-knowledge')

urlpatterns = [
    path('dashboard/', dashboard_view, name='ml-dashboard'),
    path('dashboard/data/', dashboard_data_view, name='ml-dashboard-data'),
    path('', include(router.urls)),
]
