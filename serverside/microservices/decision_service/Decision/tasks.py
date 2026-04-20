from datetime import datetime
import uuid

from celery import shared_task
from django.db import connections

from .character_generator import CharacterGenerator
from .models import Character
from .round_lifecycle import progress_round_if_due

DB_ALIAS = "betting" if "betting" in connections.databases else "default"


def _safe_unique_name(base_name: str, idx: int, max_len: int = 60) -> str:
    """
    Build a retry-safe unique character name that always fits Character.name max_length.
    """
    base = (base_name or "Agent").strip()
    # short random token avoids duplicates across Celery retries
    token = uuid.uuid4().hex[:8]
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = f"_{now}_{idx}_{token}"
    allowed_base_len = max(1, max_len - len(suffix))
    return f"{base[:allowed_base_len]}{suffix}"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def insert_characters_task(self, count: int = 5):
    generator = CharacterGenerator()
    generated = generator.generate(count=max(5, count))

    created = 0
    for idx, character in enumerate(generated, start=1):
        unique_name = _safe_unique_name(character.name, idx)
        Character.objects.using(DB_ALIAS).create(
            name=unique_name,
            stamina=character.stamina,
            control=character.control,
            power=character.power,
        )
        created += 1

    # Keep odds in sync with the newest inserted characters.
    # Run shortly after character insertion to avoid stale "previous 5" snapshots.
    try:
        from odds_generator.tasks import insert_latest_odds_task
    except Exception:
        insert_latest_odds_task = None

    if insert_latest_odds_task:
        insert_latest_odds_task.apply_async(kwargs={"limit": 5}, countdown=3)

    return {"inserted": created, "timestamp": datetime.utcnow().isoformat()}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_round_lifecycle_task(self):
    print("[Task] process_round_lifecycle_task started")
    try:
        result = progress_round_if_due()
        result["timestamp"] = datetime.utcnow().isoformat()
        print(f"[Task] process_round_lifecycle_task success: {result}")
        return result
    except Exception as e:
        print(f"[Task] process_round_lifecycle_task error: {e}")
        raise
