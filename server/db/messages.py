from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK


class InboundMessage(Base):
    __tablename__ = "inbound_message"

    msg_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_phone: Mapped[str] = mapped_column(
        String(32), ForeignKey("account.phone"), nullable=False
    )
    in_reply_to_alert_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("alert.alert_id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    received_at: Mapped[CreatedAt]
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[Optional[str]] = mapped_column(String(64))


class TriagedMessage(Base):
    __tablename__ = "triaged_message"

    msg_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("inbound_message.msg_id"), primary_key=True
    )
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    geohash6: Mapped[Optional[str]] = mapped_column(String(12))
    geohash_source: Mapped[Optional[str]] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(8))
    duplicate_of: Mapped[Optional[str]] = mapped_column(String(26))
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    bucket_key: Mapped[str] = mapped_column(String(128), nullable=False)
    body_embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))
    created_at: Mapped[CreatedAt]


class Bucket(Base):
    __tablename__ = "bucket"

    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    geohash_prefix_4: Mapped[Optional[str]] = mapped_column(String(4))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_length_ms: Mapped[int] = mapped_column(Integer, default=3000, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    claimed_by: Mapped[Optional[str]] = mapped_column(String(64))
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[CreatedAt]
