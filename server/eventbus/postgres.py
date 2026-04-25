import asyncio
from collections.abc import AsyncIterator

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresEventBus:
    """Postgres LISTEN/NOTIFY-backed event bus.

    Used by workers to wake up on new rows without polling. Channel names
    are postgres identifiers, so use ASCII-safe names like 'new_inbound',
    'bucket_open', 'toolcalls_pending', 'suggestions_pending'.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _dsn(self) -> str:
        # Convert SQLAlchemy URL to plain DSN for asyncpg.
        url = self._engine.url
        port = url.port or 5432
        return f"postgresql://{url.username}:{url.password}@{url.host}:{port}/{url.database}"

    async def publish(self, channel: str, payload: str) -> None:
        conn = await asyncpg.connect(self._dsn())
        try:
            # NOTIFY does not accept positional parameters in asyncpg — the
            # server-side NOTIFY command has no parameter slot.  We escape
            # single-quotes manually (SQL-standard doubling) and interpolate
            # directly.  Channel comes from trusted internal code only.
            escaped = payload.replace("'", "''")
            await conn.execute(f"NOTIFY {channel}, '{escaped}'")
        finally:
            await conn.close()

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        conn = await asyncpg.connect(self._dsn())
        queue: asyncio.Queue[str] = asyncio.Queue()

        def listener(_conn, _pid, _channel, payload):
            queue.put_nowait(payload)

        try:
            await conn.add_listener(channel, listener)
            while True:
                yield await queue.get()
        finally:
            await conn.remove_listener(channel, listener)
            await conn.close()

    async def close(self) -> None:
        # Per-call connections; nothing to dispose globally.
        return None
