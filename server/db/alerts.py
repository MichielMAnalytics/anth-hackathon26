from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt


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
