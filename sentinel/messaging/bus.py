"""In-process async message bus with an optional Redis Streams backend.

Kafka is intentionally avoided for the MVP; a lightweight queue is sufficient
for a single-site pilot.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any


class InProcessBus:
    """Simple asyncio queue-based pub/sub for a single process."""

    def __init__(self, maxsize: int = 1000) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, message: Any) -> None:
        await self._queue.put(message)

    async def consume(self) -> AsyncIterator[Any]:
        while True:
            item = await self._queue.get()
            yield item

    def qsize(self) -> int:
        return self._queue.qsize()
