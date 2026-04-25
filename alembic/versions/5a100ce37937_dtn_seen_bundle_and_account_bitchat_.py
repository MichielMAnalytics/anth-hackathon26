"""dtn_seen_bundle and account.bitchat_pubkey

Revision ID: 5a100ce37937
Revises: 44ee164ec4de
Create Date: 2026-04-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5a100ce37937'
down_revision: Union[str, Sequence[str], None] = '44ee164ec4de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) account.bitchat_pubkey — needed so mesh-arriving DTN bundles can
    #    resolve their Ed25519 sender pubkey back to a registered phone.
    op.add_column(
        'account',
        sa.Column('bitchat_pubkey', sa.String(length=64), nullable=True),
    )
    op.create_index(
        'ix_account_bitchat_pubkey',
        'account',
        ['bitchat_pubkey'],
        unique=False,
    )

    # 2) dtn_seen_bundle — idempotency cache. The dispatcher inserts a
    #    row per acknowledged bundle so duplicate carriers (different
    #    phones racing to deliver the same bundle) get short-circuited.
    op.create_table(
        'dtn_seen_bundle',
        sa.Column('bundle_id', sa.LargeBinary(length=16), nullable=False),
        sa.Column(
            'seen_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('last_receipt_emitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('bundle_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('dtn_seen_bundle')
    op.drop_index('ix_account_bitchat_pubkey', table_name='account')
    op.drop_column('account', 'bitchat_pubkey')
