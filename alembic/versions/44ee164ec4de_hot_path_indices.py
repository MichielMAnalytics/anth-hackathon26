"""hot_path_indices

Revision ID: 44ee164ec4de
Revises: e3fbe7836f3b
Create Date: 2026-04-25 22:33:35.667418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44ee164ec4de'
down_revision: Union[str, Sequence[str], None] = 'e3fbe7836f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Account geo prefix lookups (LIKE 'sv8d%')
    op.execute(
        "CREATE INDEX ix_account_last_known_geohash_pattern "
        "ON account (last_known_geohash text_pattern_ops)"
    )
    op.execute(
        "CREATE INDEX ix_account_home_geohash_pattern "
        "ON account (home_geohash text_pattern_ops)"
    )

    # Bucket reads
    op.execute(
        "CREATE INDEX ix_triaged_message_bucket_key ON triaged_message (bucket_key)"
    )

    # Per-sender history (note: sender_phone lives on inbound_message)
    op.execute(
        "CREATE INDEX ix_triaged_message_sender_received "
        "ON inbound_message (sender_phone, received_at DESC)"
    )

    # Recent decisions per alert
    op.execute(
        "CREATE INDEX ix_agent_decision_alert_created "
        "ON agent_decision (bucket_key, created_at DESC)"
    )

    # Worker claim queues
    op.execute(
        "CREATE INDEX ix_inbound_message_status_new "
        "ON inbound_message (status, received_at) WHERE status = 'new'"
    )
    op.execute(
        "CREATE INDEX ix_bucket_status_window "
        "ON bucket (status, window_start) WHERE status = 'open'"
    )
    op.execute(
        "CREATE INDEX ix_tool_call_pending "
        "ON tool_call (approval_status, status) WHERE status = 'pending'"
    )

    # Outbound history
    op.execute(
        "CREATE INDEX ix_outbound_message_recipient_created "
        "ON outbound_message (recipient_phone, created_at DESC)"
    )

    # AlertDelivery roster lookups
    op.execute(
        "CREATE INDEX ix_alert_delivery_alert_recipient "
        "ON alert_delivery (alert_id, recipient_phone)"
    )

    # HNSW vector indices (cosine distance)
    op.execute(
        "CREATE INDEX ix_triaged_message_body_embedding_hnsw "
        "ON triaged_message USING hnsw (body_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_notes_embedding_hnsw "
        "ON sighting USING hnsw (notes_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_cluster_embedding_hnsw "
        "ON sighting_cluster USING hnsw (embedding vector_cosine_ops)"
    )

    # Sighting + cluster geo / observer lookups
    op.execute(
        "CREATE INDEX ix_sighting_alert_geohash_recorded "
        "ON sighting (alert_id, geohash text_pattern_ops, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_observer_recorded "
        "ON sighting (observer_phone, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_cluster_alert_status_added "
        "ON sighting_cluster (alert_id, status, last_member_added_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_cluster_alert_geohash_active "
        "ON sighting_cluster (alert_id, center_geohash text_pattern_ops) "
        "WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX ix_trajectory_alert_status_extended "
        "ON trajectory (alert_id, status, last_extended_at DESC)"
    )

    # Tag lookups
    op.execute(
        "CREATE INDEX ix_tag_assignment_entity "
        "ON tag_assignment (entity_type, entity_id)"
    )
    op.execute(
        "CREATE INDEX ix_tag_assignment_tag_entity_alert "
        "ON tag_assignment (tag_id, entity_type, alert_id)"
    )

    # Heartbeat scheduler scan for active alerts
    op.execute(
        "CREATE INDEX ix_alert_active_urgency "
        "ON alert (ngo_id, status, urgency_tier) WHERE status = 'active'"
    )


def downgrade() -> None:
    for name in [
        "ix_account_last_known_geohash_pattern",
        "ix_account_home_geohash_pattern",
        "ix_triaged_message_bucket_key",
        "ix_triaged_message_sender_received",
        "ix_agent_decision_alert_created",
        "ix_inbound_message_status_new",
        "ix_bucket_status_window",
        "ix_tool_call_pending",
        "ix_outbound_message_recipient_created",
        "ix_alert_delivery_alert_recipient",
        "ix_triaged_message_body_embedding_hnsw",
        "ix_sighting_notes_embedding_hnsw",
        "ix_sighting_cluster_embedding_hnsw",
        "ix_sighting_alert_geohash_recorded",
        "ix_sighting_observer_recorded",
        "ix_sighting_cluster_alert_status_added",
        "ix_sighting_cluster_alert_geohash_active",
        "ix_trajectory_alert_status_extended",
        "ix_tag_assignment_entity",
        "ix_tag_assignment_tag_entity_alert",
        "ix_alert_active_urgency",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {name}")
