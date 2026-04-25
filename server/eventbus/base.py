from collections.abc import AsyncIterator
from typing import Protocol


class EventBus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[str]: ...

    async def close(self) -> None: ...
