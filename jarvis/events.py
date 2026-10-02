"""Durable replay plus bounded live subscriptions; slow clients cannot block workers."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from jarvis.storage import Store


class EventBus:
    def __init__(self, store: Store):
        self.store = store
        self.subscribers: set[asyncio.Queue] = set()

    async def publish(self, kind: str, data: dict[str, Any], run_id: str | None = None) -> dict:
        event = self.store.add_event(kind, data, run_id)
        for queue in tuple(self.subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
        return event

    @asynccontextmanager
    async def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self.subscribers.add(queue)
        try:
            yield queue
        finally:
            self.subscribers.discard(queue)
