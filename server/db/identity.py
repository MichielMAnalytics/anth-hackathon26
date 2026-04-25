from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt


class NGO(Base):
    __tablename__ = "ngo"

    ngo_id: Mapped[ULIDPK]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region_geohash_prefix: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    standing_orders: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_pubkey: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class Account(Base):
    __tablename__ = "account"

    phone: Mapped[str] = mapped_column(String(32), primary_key=True)
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    home_geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    last_known_geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    push_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    app_last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    channel_pref: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    sms_fallback_after_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="app", nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
