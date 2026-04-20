from celery import shared_task
from .state import advance_gameplay_tick

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def advance_global_gameplay_task(self):
    try:
        return advance_gameplay_tick()
    except Exception as exc:
        self.retry(exc=exc)