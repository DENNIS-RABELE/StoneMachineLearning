"""
Django management command to train k-means clustering models.

Usage:
    python manage.py train_clustering_model --name="model_v1" --clusters=5 --description="Initial model"
"""
from django.core.management.base import BaseCommand, CommandError
from Decision.services.kmeans_clustering import KMeansBettorClusterer
from Decision.ml_models import BettorProfile
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train a k-means clustering model on bettor data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='Name for the clustering model'
        )
        
        parser.add_argument(
            '--clusters',
            type=int,
            default=5,
            help='Number of clusters (default: 5)'
        )
        
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Description of the model'
        )
        
        parser.add_argument(
            '--random-state',
            type=int,
            default=42,
            help='Random state for reproducibility (default: 42)'
        )
        
        parser.add_argument(
            '--max-iterations',
            type=int,
            default=300,
            help='Maximum iterations for k-means (default: 300)'
        )
        
        parser.add_argument(
            '--n-init',
            type=int,
            default=10,
            help='Number of initializations (default: 10)'
        )
    
    def handle(self, *args, **options):
        model_name = options['name']
        n_clusters = options['clusters']
        description = options['description']
        random_state = options['random_state']
        max_iterations = options['max_iterations']
        n_init = options['n_init']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting training of clustering model: {model_name}')
        )
        self.stdout.write(f'  Clusters: {n_clusters}')
        self.stdout.write(f'  Random State: {random_state}')
        self.stdout.write(f'  Max Iterations: {max_iterations}')
        
        # Check bettor data availability
        total_bettors = BettorProfile.objects.count()
        if total_bettors == 0:
            raise CommandError(
                'No bettor profiles found. Please populate bettor data first.'
            )
        
        self.stdout.write(f'  Found {total_bettors} bettor profiles')
        
        if total_bettors < n_clusters:
            raise CommandError(
                f'Insufficient bettors ({total_bettors}) for {n_clusters} clusters'
            )
        
        try:
            clusterer = KMeansBettorClusterer(
                n_clusters=n_clusters,
                random_state=random_state,
                max_iterations=max_iterations,
                n_init=n_init
            )
            
            trained_model = clusterer.train(
                model_name=model_name,
                description=description
            )
            
            self.stdout.write(self.style.SUCCESS('\n✓ Model training completed successfully!'))
            self.stdout.write(f'\nModel Details:')
            self.stdout.write(f'  ID: {trained_model.id}')
            self.stdout.write(f'  Name: {trained_model.name}')
            self.stdout.write(f'  Clusters: {trained_model.n_clusters}')
            self.stdout.write(f'  Silhouette Score: {trained_model.silhouette_score:.4f}')
            self.stdout.write(f'  Davies-Bouldin Index: {trained_model.davies_bouldin_score:.4f}')
            self.stdout.write(f'  Inertia: {trained_model.inertia:.4f}')
            self.stdout.write(f'  Samples Trained: {trained_model.num_samples_trained}')
            
        except ValueError as e:
            raise CommandError(f'Validation error: {str(e)}')
        except Exception as e:
            logger.error(f'Error training model: {str(e)}', exc_info=True)
            raise CommandError(f'Error during model training: {str(e)}')
