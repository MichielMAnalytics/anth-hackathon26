from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK
from server.db import decisions  # noqa: F401  (registers tool_call table on Base.metadata)


class OutboundMessage(Base):
    __tablename__ = "outbound_message"

    out_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(26), ForeignKey("tool_call.call_id"))
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    provider_msg_id: Mapped[Optional[str]] = mapped_column(String(128))
    error: Mapped[Optional[str]] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    previous_out_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("outbound_message.out_id")
    )
    created_at: Mapped[CreatedAt]


class Sighting(Base):
    __tablename__ = "sighting"

    sighting_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    observer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    geohash: Mapped[str] = mapped_column(String(12), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    photo_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    notes_embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))
    recorded_at: Mapped[CreatedAt]
