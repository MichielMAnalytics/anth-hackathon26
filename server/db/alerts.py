import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt

# 29 chars, no vowels (avoids accidental words) and no 0/1/I/O (confusables).
REPLY_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXYZ23456789"
REPLY_CODE_LEN = 4


def random_reply_code() -> str:
    return "".join(secrets.choice(REPLY_CODE_ALPHABET) for _ in range(REPLY_CODE_LEN))


async def generate_reply_code(db: AsyncSession, ngo_id: str) -> str:
    """Pick a code unique among this NGO's currently-active alerts."""
    for _ in range(20):
        code = random_reply_code()
        clash = (
            await db.execute(
                select(Alert.alert_id).where(
                    Alert.ngo_id == ngo_id,
                    Alert.reply_code == code,
                    Alert.status == "active",
                )
            )
        ).scalar_one_or_none()
        if clash is None:
            return code
    raise RuntimeError("could not allocate unique reply_code after 20 tries")


class Alert(Base):
    __tablename__ = "alert"

    alert_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(1024))
    last_seen_geohash: Mapped[Optional[str]] = mapped_column(String(12))
    description: Mapped[Optional[str]] = mapped_column(Text)
    region_geohash_prefix: Mapped[Optional[str]] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # 4-char civilian-facing code used to thread inbound replies back onto
    # this case (see server/api/webhooks.py). Unique per NGO among active
    # alerts; freed when the alert moves to resolved/archived.
    reply_code: Mapped[Optional[str]] = mapped_column(String(4))
    # Categorization (set by agent via categorize_alert; defaults nullable):
    category: Mapped[Optional[str]] = mapped_column(String(64))
    urgency_tier: Mapped[Optional[str]] = mapped_column(String(16))
    urgency_score: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class AlertDelivery(Base):
    __tablename__ = "alert_delivery"

    delivery_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    out_id: Mapped[Optional[str]] = mapped_column(String(26))   # FK→OutboundMessage added later
    sent_at: Mapped[CreatedAt]
