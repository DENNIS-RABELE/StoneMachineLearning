from asgiref.sync import async_to_sync
try:
    from channels.layers import get_channel_layer
except ImportError:
    def get_channel_layer():
        return None

from django.db import transaction
from django.db import router
from django.utils import timezone
from .models import GlobalGameplayState

GROUP_NAME = "global_gameplay"


def _gameplay_db_alias() -> str:
    return router.db_for_write(GlobalGameplayState) or "default"

def get_global_gameplay_state() -> GlobalGameplayState:
    db_alias = _gameplay_db_alias()
    state, _ = GlobalGameplayState.objects.using(db_alias).get_or_create(key="global")
    return state

def serialize_state(state: GlobalGameplayState) -> dict:
    return {
        "status": state.status,
        "tick": int(state.tick),
        "max_ticks": int(state.max_ticks),
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "stopped_at": state.stopped_at.isoformat() if state.stopped_at else None,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }

def broadcast_state(payload: dict) -> None:
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(
            GROUP_NAME,
            {"type": "gameplay.state", "payload": payload},
        )

def _publish_and_broadcast(state: GlobalGameplayState, update_fields: list[str]) -> dict:
    state.save(using=state._state.db, update_fields=update_fields)
    payload = serialize_state(state)
    broadcast_state(payload)
    return payload

def start_gameplay(*, max_ticks: int | None = None, reset_tick: bool = False) -> dict:
    db_alias = _gameplay_db_alias()
    with transaction.atomic(using=db_alias):
        state = GlobalGameplayState.objects.using(db_alias).select_for_update().get_or_create(key="global")[0]
        if max_ticks is not None and max_ticks > 0:
            state.max_ticks = int(max_ticks)
        if reset_tick:
            state.tick = 0
        state.status = GlobalGameplayState.STATUS_RUNNING
        state.started_at = timezone.now()
        state.stopped_at = None
        return _publish_and_broadcast(state, ["status", "tick", "max_ticks", "started_at", "stopped_at", "updated_at"])

def stop_gameplay() -> dict:
    db_alias = _gameplay_db_alias()
    with transaction.atomic(using=db_alias):
        state = GlobalGameplayState.objects.using(db_alias).select_for_update().get_or_create(key="global")[0]
        state.status = GlobalGameplayState.STATUS_STOPPED
        state.stopped_at = timezone.now()
        return _publish_and_broadcast(state, ["status", "stopped_at", "updated_at"])

def reset_gameplay(*, max_ticks: int | None = None) -> dict:
    db_alias = _gameplay_db_alias()
    with transaction.atomic(using=db_alias):
        state = GlobalGameplayState.objects.using(db_alias).select_for_update().get_or_create(key="global")[0]
        state.tick = 0
        state.status = GlobalGameplayState.STATUS_STOPPED
        state.started_at = None
        state.stopped_at = timezone.now()
        if max_ticks is not None and max_ticks > 0:
            state.max_ticks = int(max_ticks)
        return _publish_and_broadcast(state, ["tick", "status", "started_at", "stopped_at", "max_ticks", "updated_at"])

def advance_gameplay_tick() -> dict:
    db_alias = _gameplay_db_alias()
    with transaction.atomic(using=db_alias):
        state = GlobalGameplayState.objects.using(db_alias).select_for_update().get_or_create(key="global")[0]
        if state.status != GlobalGameplayState.STATUS_RUNNING:
            return serialize_state(state)

        state.tick += 1
        if state.tick >= state.max_ticks:
            state.status = GlobalGameplayState.STATUS_STOPPED
            state.stopped_at = timezone.now()

        return _publish_and_broadcast(state, ["tick", "status", "stopped_at", "updated_at"])
    
def publish_snapshot() -> dict:
    state = get_global_gameplay_state()
    payload = serialize_state(state)
    broadcast_state(payload)
    return payload
