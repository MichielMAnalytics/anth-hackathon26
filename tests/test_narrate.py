"""Unit tests for the narrate_decision util.

Covers the verb-led one-liners the dashboard tape and reasoning drawer
read directly. Stays at the pure-function level (no DB) so it's fast
and deterministic.
"""
from __future__ import annotations

from server.workers.narrate import narrate_call, narrate_decision


class _Alert:
    def __init__(self, person_name: str = "Tamar"):
        self.person_name = person_name


def _call(name: str, args: dict, mode: str = "execute") -> dict:
    return {"tool_name": name, "args": args, "mode": mode}


def test_narrate_record_sighting_includes_geohash_and_confidence():
    s = narrate_call(
        "record_sighting",
        {"geohash": "sv8d6f", "observer_phone": "+9647000000010", "confidence": 0.82},
        "execute",
    )
    assert "sv8d6f" in s
    assert "0.82" in s
    assert "Logged sighting" in s


def test_narrate_send_one_includes_recipient_phone_excerpt():
    s = narrate_call(
        "send",
        {"audience": {"type": "one", "phone": "+9647000000010"},
         "bodies": {"en": "Thanks — your sighting is recorded."}},
        "execute",
    )
    assert "Acked" in s or "Sent" in s
    assert "+964" in s  # phone excerpt present


def test_narrate_send_suggest_to_audience_id_calls_out_approval():
    s = narrate_call(
        "send",
        {"audience": {"type": "audience_id", "id": "verified_eyewitnesses"},
         "bodies": {"en": "Update on the case."}},
        "suggest",
    )
    assert "Wants to broadcast" in s
    assert "approval" in s.lower()


def test_narrate_categorize_alert_suggest_calls_out_approval():
    s = narrate_call(
        "categorize_alert",
        {"category": "missing_person", "urgency_tier": "critical", "urgency_score": 0.94,
         "alert_id": "01J", "reason": "high density"},
        "suggest",
    )
    assert "missing_person" in s
    assert "critical" in s
    assert "approval" in s.lower()


def test_narrate_noop_says_reviewed():
    s = narrate_call("noop", {"reason": "no actionable messages in bucket"}, "execute")
    assert "Reviewed" in s


def test_narrate_decision_combines_two_calls_with_and():
    calls = [
        _call("record_sighting", {"geohash": "sv8d6f", "observer_phone": "+9647000000010",
                                  "confidence": 0.78}),
        _call("send", {"audience": {"type": "one", "phone": "+9647000000010"},
                       "bodies": {"en": "Thanks — your sighting is recorded."}}),
    ]
    s = narrate_decision(calls, alert=_Alert(person_name="Tamar"))
    assert "Logged sighting" in s
    assert "and" in s.lower()
    assert "Tamar" in s


def test_narrate_decision_drops_noop_when_real_action_present():
    calls = [
        _call("noop", {"reason": "consolidation"}),
        _call("record_sighting", {"geohash": "sv8d6f", "observer_phone": "+9647000000010",
                                  "confidence": 0.85}),
    ]
    s = narrate_decision(calls, alert=None)
    assert "Logged sighting" in s
    assert "Reviewed" not in s


def test_narrate_decision_heartbeat_with_no_calls():
    s = narrate_decision([], alert=_Alert(), is_heartbeat=True)
    assert "Heartbeat" in s


def test_narrate_decision_three_or_more_collapses_with_count():
    calls = [
        _call("record_sighting", {"geohash": "sv8d6f", "observer_phone": "+1", "confidence": 0.8}),
        _call("send", {"audience": {"type": "one", "phone": "+1"}, "bodies": {"en": "ok"}}),
        _call("apply_tag", {"entity_type": "sighting", "entity_id": "01ABC", "tag_name": "verified"}),
    ]
    s = narrate_decision(calls)
    assert "+1 more" in s or "+2 more" in s


def test_narrate_decision_does_not_double_mention_subject():
    """If sentence already contains person name, don't append it again."""
    calls = [
        _call("escalate_to_ngo", {"reason": "x", "summary": "Tamar — conflicting reports"}),
    ]
    s = narrate_decision(calls, alert=_Alert(person_name="Tamar"))
    # Should appear once (from summary) and not duplicated by alert append.
    assert s.lower().count("tamar") == 1
