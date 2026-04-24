"""
Async Event Bus — Decoupled pub/sub for internal progress notifications.

Design Pattern: Observer / Pub-Sub
- Producers publish events without knowing who listens
- Consumers subscribe without knowing who produces
- Replaces direct asyncio.Queue manipulation in IngestTaskManager
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict], Awaitable[None]]


class EventBus:
    """
    In-memory async event bus.

    Thread-safe for asyncio context. Supports typed event channels.
    Can be swapped for Redis/RabbitMQ implementation later without
    changing producers or consumers.
    """

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, payload: dict) -> None:
        """Publish an event to all subscribers of the given type."""
        async with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        if not handlers:
            return

        # Run handlers concurrently; isolate failures
        results = await asyncio.gather(
            *[self._safe_call(h, payload) for h in handlers],
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"EventBus handler {i} for {event_type} failed: {result}")

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""
        async with self._lock:
            self._subscribers.setdefault(event_type, [])
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a handler. Safe to call even if not subscribed."""
        async with self._lock:
            handlers = self._subscribers.get(event_type, [])
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    @staticmethod
    async def _safe_call(handler: EventHandler, payload: dict) -> None:
        await handler(payload)
