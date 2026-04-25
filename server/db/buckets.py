from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.messages import Bucket


async def claim_open_bucket(
    session: AsyncSession,
    worker_id: str,
) -> Optional[Bucket]:
    """Atomically claim one open bucket; transition to 'claimed'.

    Uses FOR UPDATE SKIP LOCKED so concurrent workers don't fight over the
    same row. Returns None if no open bucket is available.
    """
    row = (
        await session.execute(
            text(
                """
                SELECT bucket_key
                FROM bucket
                WHERE status = 'open'
                ORDER BY window_start
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
        )
    ).first()
    if row is None:
        return None

    bucket = await session.get(Bucket, row[0])
    if bucket is None or bucket.status != "open":
        return None
    bucket.status = "claimed"
    bucket.claimed_by = worker_id
    bucket.claimed_at = datetime.now(UTC)
    await session.commit()
    return bucket


async def mark_bucket_done(session: AsyncSession, bucket_key: str) -> None:
    bucket = await session.get(Bucket, bucket_key)
    if bucket is None:
        return
    bucket.status = "done"
    await session.commit()


async def release_bucket(session: AsyncSession, bucket_key: str) -> None:
    """Release a claimed bucket back to 'open' for retry."""
    bucket = await session.get(Bucket, bucket_key)
    if bucket is None:
        return
    bucket.status = "open"
    bucket.claimed_by = None
    bucket.claimed_at = None
    bucket.retry_count = (bucket.retry_count or 0) + 1
    await session.commit()


async def fail_bucket(session: AsyncSession, bucket_key: str) -> None:
    bucket = await session.get(Bucket, bucket_key)
    if bucket is None:
        return
    bucket.status = "failed"
    await session.commit()


def _alert_lock_key(alert_id: str) -> int:
    """Stable signed-int64 lock key for pg_try_advisory_lock(bigint)."""
    return int.from_bytes(alert_id.encode("utf-8")[:8].ljust(8, b"\0"), "big", signed=True)


async def try_advisory_lock(session: AsyncSession, alert_id: str) -> bool:
    """Acquire a per-alert advisory lock. Returns True on success."""
    key = _alert_lock_key(alert_id)
    row = (
        await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
    ).scalar()
    return bool(row)


async def release_advisory_lock(session: AsyncSession, alert_id: str) -> None:
    key = _alert_lock_key(alert_id)
    await session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
    await session.commit()
