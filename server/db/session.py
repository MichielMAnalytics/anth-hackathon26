from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from server.db.engine import get_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_maker()() as session:
        yield session
