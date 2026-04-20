"""Celery tasks for ML module - periodic data generation and model training."""
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_sample_bettors_task(self):
    """
    Periodic task to generate new sample bettor data.
    Runs every 12 hours by default.
    """
    try:
        logger.info("Starting automatic bettor sample generation...")
        call_command(
            'generate_sample_bettors',
            count=100,
            seed=None,
            clear=False,  # Keep existing data, just add new
        )
        logger.info("✓ Successfully generated sample bettors")
        return "Sample bettors generated successfully"
    except Exception as exc:
        logger.error(f"Error generating sample bettors: {exc}")
        # Retry in 5 minutes if it fails
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def train_clustering_model_task(self):
    """
    Periodic task to retrain clustering model.
    Runs every 24 hours by default.
    """
    try:
        logger.info("Starting automatic clustering model training...")
        
        # Generate unique model name with timestamp
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"auto_trained_{timestamp}"
        
        call_command(
            'train_clustering_model',
            name=model_name,
            clusters=5,
            description=f'Auto-trained model at {timezone.now().isoformat()}',
            random_state=42,
            max_iterations=300,
            n_init=10,
        )
        logger.info(f"✓ Successfully trained model: {model_name}")
        return f"Model trained successfully: {model_name}"
    except Exception as exc:
        logger.error(f"Error training clustering model: {exc}")
        # Retry in 30 minutes if it fails
        raise self.retry(exc=exc, countdown=1800)


@shared_task(bind=True)
def activate_latest_model_task(self):
    """
    Periodic task to activate the latest trained model.
    Runs every 24 hours, 1 hour after training.
    """
    try:
        from .models import ClusteringModel
        
        logger.info("Activating latest clustering model...")
        
        # Get the most recently trained model
        latest_model = ClusteringModel.objects.filter(is_active=False).order_by('-trained_at').first()
        
        if latest_model:
            # Deactivate all other models
            ClusteringModel.objects.exclude(id=latest_model.id).update(is_active=False)
            latest_model.is_active = True
            latest_model.save()
            logger.info(f"✓ Activated model: {latest_model.name}")
            return f"Model activated: {latest_model.name}"
        else:
            logger.info("No new models to activate")
            return "No new models to activate"
    except Exception as exc:
        logger.error(f"Error activating model: {exc}")
        raise self.retry(exc=exc, countdown=300)
