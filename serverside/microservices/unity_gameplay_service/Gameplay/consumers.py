import logging
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .state import GROUP_NAME, get_global_gameplay_state, serialize_state

logger = logging.getLogger(__name__)

class GlobalGameplayConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send_json(await self._snapshot_message())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "snapshot":
            await self.send_json(await self._snapshot_message())

    async def gameplay_state(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _snapshot_message(self):
        try:
            state = get_global_gameplay_state()
            return serialize_state(state)
        except Exception as e:
            logger.error(f"Failed to fetch gameplay state snapshot: {e}")
            return {"error": "state_unavailable"}