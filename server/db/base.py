from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column
from ulid import ULID


def generate_ulid() -> str:
    return str(ULID())


class Base(DeclarativeBase):
    """Declarative base with sensible Postgres defaults."""


# Type alias for ULID primary keys, consistent across all tables.
ULIDPK = Mapped[
    Annotated[
        str,
        mapped_column(String(26), primary_key=True, default=generate_ulid),
    ]
]

# Created/updated timestamps used on every queue table.
CreatedAt = Mapped[
    Annotated[
        datetime,
        mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    ]
]

UpdatedAt = Mapped[
    Annotated[
        datetime,
        mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    ]
]
