"""alert reply_code

Revision ID: f161156456ad
Revises: 44ee164ec4de
Create Date: 2026-04-26 12:00:00.000000

Adds a 4-char civilian-facing code per active alert so inbound SMS
replies prefixed with the code can be threaded back onto the case.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from server.db.alerts import random_reply_code


revision: str = "f161156456ad"
down_revision: Union[str, Sequence[str], None] = "44ee164ec4de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alert", sa.Column("reply_code", sa.String(length=4), nullable=True))

    # Backfill existing rows with a unique-per-(ngo, active) code.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT alert_id, ngo_id, status FROM alert")
    ).fetchall()
    used: dict[str, set[str]] = {}
    for row in rows:
        if row.status != "active":
            continue
        bucket = used.setdefault(row.ngo_id, set())
        for _ in range(40):
            code = random_reply_code()
            if code not in bucket:
                bucket.add(code)
                bind.execute(
                    sa.text("UPDATE alert SET reply_code = :c WHERE alert_id = :a"),
                    {"c": code, "a": row.alert_id},
                )
                break

    op.create_index(
        "uq_alert_reply_code_active",
        "alert",
        ["ngo_id", "reply_code"],
        unique=True,
        postgresql_where=sa.text("reply_code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_alert_reply_code_active", table_name="alert")
    op.drop_column("alert", "reply_code")
