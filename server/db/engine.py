from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from server.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, future=True)


@lru_cache
def get_session_maker() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
