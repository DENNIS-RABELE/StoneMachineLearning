from datetime import datetime

from celery import shared_task

from Generator.services import sync_latest_character_odds


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def insert_latest_odds_task(self, limit: int = 5):
    result = sync_latest_character_odds(limit=max(1, limit))
    result["timestamp"] = datetime.utcnow().isoformat()
    return result
