from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK


class AgentDecision(Base):
    __tablename__ = "agent_decision"
    __table_args__ = (UniqueConstraint("bucket_key", name="uq_agent_decision_bucket_key"),)

    decision_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    bucket_key: Mapped[str] = mapped_column(
        String(128), ForeignKey("bucket.bucket_key"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text)
    tool_calls: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    turns: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    total_turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[CreatedAt]


class ToolCall(Base):
    __tablename__ = "tool_call"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_tool_call_idempotency_key"),
    )

    call_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    decision_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("agent_decision.decision_id")
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_by: Mapped[Optional[str]] = mapped_column(String(64))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revised_from_call_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("tool_call.call_id")
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[Optional[str]] = mapped_column(String(64))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[CreatedAt]
