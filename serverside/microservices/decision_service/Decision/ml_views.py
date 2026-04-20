"""
API views for machine learning clustering functionality.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg
import logging

from Decision.ml_models import (
    BettorProfile, ClusteringModel, BettorCluster,
    ClusterCharacteristics, MLMetrics
)
from Decision.ml_serializers import (
    BettorProfileSerializer, ClusteringModelSerializer,
    ClusterCharacteristicsSerializer, BettorClusterSerializer,
    TrainClusteringModelSerializer, PredictClusterSerializer,
    ClusterInsightSerializer, MLMetricsSerializer
)
from Decision.services.kmeans_clustering import KMeansBettorClusterer
from Decision.services.data_preprocessing import (
    BettorDataAggregator, DataValidationService
)

logger = logging.getLogger(__name__)


class BettorProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for bettor profiles."""
    
    queryset = BettorProfile.objects.all()
    serializer_class = BettorProfileSerializer
    lookup_field = 'bettor_id'
    lookup_value_regex = '[^/]+'
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by minimum bets
        min_bets = self.request.query_params.get('min_bets')
        if min_bets:
            queryset = queryset.filter(total_bets__gte=int(min_bets))
        
        # Filter by win rate range
        min_win_rate = self.request.query_params.get('min_win_rate')
        max_win_rate = self.request.query_params.get('max_win_rate')
        if min_win_rate:
            queryset = queryset.filter(win_rate__gte=float(min_win_rate))
        if max_win_rate:
            queryset = queryset.filter(win_rate__lte=float(max_win_rate))
        
        # Filter by ROI
        min_roi = self.request.query_params.get('min_roi')
        if min_roi:
            queryset = queryset.filter(roi__gte=float(min_roi))
        
        return queryset.order_by('-total_bets')
    
    @action(detail=False, methods=['post'])
    def update_from_history(self, request):
        """Update a bettor profile from their betting history."""
        bettor_id = request.data.get('bettor_id')
        betting_history = request.data.get('betting_history', [])
        time_window_days = request.data.get('time_window_days')
        
        if not bettor_id:
            return Response(
                {'error': 'bettor_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profile = BettorDataAggregator.update_bettor_profile_from_betting_history(
                bettor_id=bettor_id,
                betting_history=betting_history,
                time_window_days=time_window_days
            )
            
            serializer = self.get_serializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """Batch update multiple bettor profiles."""
        bettor_betting_data = request.data.get('bettor_betting_data', {})
        time_window_days = request.data.get('time_window_days')
        
        try:
            profiles = BettorDataAggregator.batch_update_profiles(
                bettor_betting_data=bettor_betting_data,
                time_window_days=time_window_days
            )
            
            serializer = self.get_serializer(profiles, many=True)
            return Response(
                {'updated_count': len(profiles), 'profiles': serializer.data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error batch updating profiles: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ClusteringModelViewSet(viewsets.ModelViewSet):
    """ViewSet for clustering models."""
    
    queryset = ClusteringModel.objects.all()
    serializer_class = ClusteringModelSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('-trained_at')
    
    @action(detail=False, methods=['post'])
    def train_model(self, request):
        """Train a new k-means clustering model."""
        serializer = TrainClusteringModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        model_name = serializer.validated_data['model_name']
        
        # Check if model with this name already exists
        if ClusteringModel.objects.filter(name=model_name).exists():
            return Response(
                {'error': f'Model with name "{model_name}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            logger.info(f"Starting training of model: {model_name}")
            
            clusterer = KMeansBettorClusterer(
                n_clusters=serializer.validated_data.get('n_clusters', 5),
                random_state=serializer.validated_data.get('random_state', 42),
                max_iterations=serializer.validated_data.get('max_iterations', 300),
                n_init=serializer.validated_data.get('n_init', 10)
            )
            
            trained_model = clusterer.train(
                model_name=model_name,
                description=serializer.validated_data.get('description', '')
            )
            
            model_serializer = self.get_serializer(trained_model)
            return Response(model_serializer.data, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            logger.error(f"Validation error during training: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error during model training: {str(e)}")
            return Response(
                {'error': f'Model training failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def cluster_summary(self, request, pk=None):
        """Get detailed summary of all clusters in a model."""
        clustering_model = self.get_object()
        
        try:
            clusterer = KMeansBettorClusterer(n_clusters=clustering_model.n_clusters)
            summary = clusterer.get_all_clusters_summary(clustering_model)
            
            return Response(summary, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error generating cluster summary: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def cluster_detail(self, request, pk=None):
        """Get detailed information about a specific cluster."""
        clustering_model = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if cluster_id is None:
            return Response(
                {'error': 'cluster_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cluster_id = int(cluster_id)
            
            characteristics = get_object_or_404(
                ClusterCharacteristics,
                model=clustering_model,
                cluster_id=cluster_id
            )
            
            clusterer = KMeansBettorClusterer(n_clusters=clustering_model.n_clusters)
            insight = clusterer.get_cluster_insights(clustering_model, cluster_id)
            
            return Response(insight, status=status.HTTP_200_OK)
        except ValueError:
            return Response(
                {'error': 'cluster_id must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error retrieving cluster details: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def set_active(self, request, pk=None):
        """Set a model as the active clustering model."""
        clustering_model = self.get_object()
        
        # Deactivate all other models
        ClusteringModel.objects.exclude(pk=clustering_model.pk).update(is_active=False)
        
        # Activate this model
        clustering_model.is_active = True
        clustering_model.save()
        
        serializer = self.get_serializer(clustering_model)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BettorClusterViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for bettor cluster assignments."""
    
    queryset = BettorCluster.objects.all()
    serializer_class = BettorClusterSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by model
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)
        
        # Filter by cluster
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)
        
        # Filter by bettor
        bettor_id = self.request.query_params.get('bettor_id')
        if bettor_id:
            queryset = queryset.filter(bettor_profile__bettor_id=bettor_id)
        
        return queryset.select_related('bettor_profile', 'model')
    
    @action(detail=False, methods=['post'])
    def predict_cluster(self, request):
        """Predict cluster for a bettor using active model."""
        serializer = PredictClusterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        bettor_id = serializer.validated_data['bettor_id']
        
        try:
            # Get active model
            active_model = ClusteringModel.objects.filter(is_active=True).first()
            if not active_model:
                return Response(
                    {'error': 'No active clustering model'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get bettor profile
            bettor_profile = get_object_or_404(
                BettorProfile,
                bettor_id=bettor_id
            )
            
            # Predict cluster
            clusterer = KMeansBettorClusterer(n_clusters=active_model.n_clusters)
            cluster_id, confidence = clusterer.predict_cluster(
                bettor_profile,
                active_model
            )
            
            return Response({
                'bettor_id': bettor_id,
                'cluster_id': cluster_id,
                'confidence': confidence,
                'model_id': active_model.id,
                'model_name': active_model.name
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error predicting cluster: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MLMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ML metrics tracking."""
    
    queryset = MLMetrics.objects.all()
    serializer_class = MLMetricsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by model
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)
        
        # Filter by metric type
        metric_type = self.request.query_params.get('metric_type')
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        return queryset.order_by('-timestamp')
