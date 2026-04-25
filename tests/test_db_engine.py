from sqlalchemy import text

from server.db.engine import get_engine


async def test_engine_connects_and_pgvector_loaded():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

        # pgvector extension must be loaded
        ext = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        assert ext.scalar() == "vector"
    await engine.dispose()


async def test_test_db_url_is_separate(test_engine):
    # The test_engine fixture should point at matching_test, not matching.
    assert "matching_test" in str(test_engine.url)
