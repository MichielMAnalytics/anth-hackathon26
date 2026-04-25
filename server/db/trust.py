from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt


class BadActor(Base):
    __tablename__ = "bad_actor"

    phone: Mapped[str] = mapped_column(String(32), primary_key=True)
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    marked_by: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
