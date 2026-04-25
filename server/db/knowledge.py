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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt


class SightingCluster(Base):
    __tablename__ = "sighting_cluster"

    cluster_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    center_geohash: Mapped[str] = mapped_column(String(12), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    time_window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    time_window_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sighting_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    sighting_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mean_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    merged_into: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("sighting_cluster.cluster_id")
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    last_member_added_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Trajectory(Base):
    __tablename__ = "trajectory"

    trajectory_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    points: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    direction_deg: Mapped[Optional[float]] = mapped_column(Float)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    last_extended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (
        UniqueConstraint("ngo_id", "namespace", "name", name="uq_tag_ngo_ns_name"),
    )

    tag_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(16), default="agent", nullable=False)
    created_at: Mapped[CreatedAt]


class TagAssignment(Base):
    __tablename__ = "tag_assignment"
    __table_args__ = (
        UniqueConstraint(
            "tag_id", "entity_type", "entity_id", name="uq_tag_assignment_tag_entity"
        ),
    )

    assignment_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(26), ForeignKey("tag.tag_id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(26), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    applied_by: Mapped[str] = mapped_column(String(16), default="agent", nullable=False)
    applied_by_id: Mapped[Optional[str]] = mapped_column(String(64))
    alert_id: Mapped[Optional[str]] = mapped_column(String(26), ForeignKey("alert.alert_id"))
    created_at: Mapped[CreatedAt]
