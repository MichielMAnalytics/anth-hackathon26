from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, mapped_column
from ulid import ULID


def generate_ulid() -> str:
    return str(ULID())


class Base(DeclarativeBase):
    """Declarative base with sensible Postgres defaults."""


# Type aliases for use as `Mapped[ULIDPK]`, `Mapped[CreatedAt]`, `Mapped[UpdatedAt]`
# in subclasses. The SQLAlchemy 2.0 declarative pattern wraps the alias with
# `Mapped[...]` at the use site (see model files in subsequent tasks).
ULIDPK = Annotated[
    str,
    mapped_column(String(26), primary_key=True, default=generate_ulid),
]

CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]

UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]
