from sqlalchemy import text


REQUIRED_INDEXES = {
    # name pattern → table
    "ix_account_last_known_geohash_pattern": "account",
    "ix_account_home_geohash_pattern": "account",
    "ix_triaged_message_bucket_key": "triaged_message",
    "ix_triaged_message_sender_received": "inbound_message",
    "ix_agent_decision_alert_created": "agent_decision",
    "ix_inbound_message_status_new": "inbound_message",
    "ix_bucket_status_window": "bucket",
    "ix_outbound_message_recipient_created": "outbound_message",
    "ix_alert_delivery_alert_recipient": "alert_delivery",
    "ix_tool_call_pending": "tool_call",
    "ix_triaged_message_body_embedding_hnsw": "triaged_message",
    "ix_sighting_notes_embedding_hnsw": "sighting",
    "ix_sighting_cluster_embedding_hnsw": "sighting_cluster",
    "ix_sighting_alert_geohash_recorded": "sighting",
    "ix_sighting_observer_recorded": "sighting",
    "ix_sighting_cluster_alert_status_added": "sighting_cluster",
    "ix_sighting_cluster_alert_geohash_active": "sighting_cluster",
    "ix_trajectory_alert_status_extended": "trajectory",
    "ix_tag_assignment_entity": "tag_assignment",
    "ix_tag_assignment_tag_entity_alert": "tag_assignment",
    "ix_alert_active_urgency": "alert",
}


async def test_all_required_indexes_exist(db):
    found = (
        await db.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public'"
            )
        )
    ).scalars().all()
    missing = [name for name in REQUIRED_INDEXES if name not in found]
    assert not missing, f"missing indices: {missing}"
