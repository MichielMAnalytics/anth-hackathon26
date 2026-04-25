"""Per-bundle idempotency cache.

The hub may receive the same DTN bundle multiple times — different
carriers each finish the gossip race. We acknowledge the first arrival,
emit the receipt, and silently treat subsequent arrivals as duplicates.

This module backs the `GET /app/dtn/seen?ids=...` endpoint a teammate
will mount on the API tier (so internet-bearing carriers can probe
before re-flooding) as well as the in-process dispatcher dedup check.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import DateTime, LargeBinary, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt


class DTNSeenBundle(Base):
    """Records every bundle_id the hub has acknowledged.

    Insert-ignore on conflict so concurrent dispatcher calls for the
    same bundle don't error out — the first wins.
    """

    __tablename__ = "dtn_seen_bundle"

    bundle_id: Mapped[bytes] = mapped_column(LargeBinary(length=16), primary_key=True)
    seen_at: Mapped[CreatedAt]
    last_receipt_emitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SeenStore:
    """Thin async wrapper around `DTNSeenBundle` used by the dispatcher
    and the friend's `/app/dtn/seen` endpoint."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_seen(self, bundle_id: bytes) -> bool:
        row = await self.db.execute(
            select(DTNSeenBundle).where(DTNSeenBundle.bundle_id == bundle_id)
        )
        return row.first() is not None

    async def mark_seen(self, bundle_id: bytes) -> bool:
        """Record a `bundle_id` as seen. Returns True iff this was a new
        record (first arrival), False if it was already present
        (duplicate carrier)."""
        stmt = (
            pg_insert(DTNSeenBundle)
            .values(bundle_id=bundle_id)
            .on_conflict_do_nothing(index_elements=["bundle_id"])
            .returning(DTNSeenBundle.bundle_id)
        )
        result = await self.db.execute(stmt)
        return result.first() is not None

    async def filter_unseen(self, bundle_ids: Iterable[bytes]) -> list[bytes]:
        ids = list(bundle_ids)
        if not ids:
            return []
        rows = await self.db.execute(
            select(DTNSeenBundle.bundle_id).where(DTNSeenBundle.bundle_id.in_(ids))
        )
        seen = {b for (b,) in rows.all()}
        return [bid for bid in ids if bid not in seen]
