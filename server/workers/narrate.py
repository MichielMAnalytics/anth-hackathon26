"""Plain-English narrations of agent decisions.

The dashboard's activity tape, "now playing" panel, and approvals inbox
all need a one-line sentence describing what the agent did (or wants to
do). We generate that here from the staged tool calls + alert context,
so both stub-mode and real-mode produce the same human-readable surface.

Goals:
- Verb-led, present-perfect or future-conditional ("Logged…", "Wants to…")
- Mention the case subject when relevant ("…for Amira Hassan")
- Mention numbers / sizes when they matter ("…to 1,540 eyewitnesses")
- Stay one sentence, ~140 chars max
"""

from __future__ import annotations

from typing import Any, Optional


def _truncate(text: str, max_len: int = 140) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _short_phone(phone: Optional[str]) -> str:
    if not phone:
        return "an observer"
    if len(phone) > 8:
        return f"{phone[:4]}…{phone[-3:]}"
    return phone


def _audience_size_label(audience: dict) -> str:
    """Best-effort human label for an audience selector."""
    t = audience.get("type")
    if t == "one":
        return _short_phone(audience.get("phone"))
    if t == "many":
        n = len(audience.get("phones") or [])
        return f"{n} recipients"
    if t == "region":
        prefix = audience.get("geohash_prefix") or "a region"
        return f"everyone in {prefix}"
    if t == "all_alert":
        return "everyone the alert was sent to"
    if t == "all_ngo":
        return "all NGO contacts"
    if t == "audience_id":
        return audience.get("id") or "an audience"
    return "an audience"


def _audience_count(audience: dict) -> Optional[int]:
    if audience.get("type") == "one":
        return 1
    if audience.get("type") == "many":
        return len(audience.get("phones") or [])
    return None


def _narrate_send(args: dict, mode: str) -> str:
    audience = args.get("audience") or {}
    bodies = args.get("bodies") or {}
    label = _audience_size_label(audience)
    count = _audience_count(audience)

    if mode == "suggest":
        if audience.get("type") in ("region", "audience_id", "all_alert", "all_ngo"):
            return f"Wants to broadcast to {label} — awaiting your approval"
        return f"Drafted a message to {label} — awaiting your approval"

    # execute mode
    if count == 1:
        body = next(iter(bodies.values()), "") if bodies else ""
        snippet = body[:60].rstrip()
        if snippet:
            return f"Acked {label}: \"{snippet}\""
        return f"Sent a reply to {label}"
    return f"Sent a message to {label}"


def _narrate_record_sighting(args: dict) -> str:
    geohash = args.get("geohash") or "the area"
    observer = _short_phone(args.get("observer_phone"))
    conf = args.get("confidence")
    conf_str = f" (conf {float(conf):.2f})" if conf is not None else ""
    return f"Logged sighting near {geohash} from {observer}{conf_str}"


def _narrate_upsert_cluster(args: dict) -> str:
    label = args.get("label") or "a cluster"
    n = len(args.get("sighting_ids") or [])
    return f"Updated cluster \"{label}\" with {n} sightings"


def _narrate_merge_clusters(args: dict) -> str:
    n = len(args.get("source_cluster_ids") or [])
    return f"Merged {n} cluster{'s' if n != 1 else ''} into one"


def _narrate_upsert_trajectory(args: dict) -> str:
    deg = args.get("direction_deg")
    speed = args.get("speed_kmh")
    if deg is not None and speed is not None:
        return f"Updated trajectory — heading {round(float(deg))}° at {speed} km/h"
    return "Updated trajectory for the case"


def _narrate_apply_tag(args: dict) -> str:
    return f"Tagged {args.get('entity_type')} {args.get('entity_id', '')[:8]} as \"{args.get('tag_name')}\""


def _narrate_remove_tag(args: dict) -> str:
    return f"Removed tag \"{args.get('tag_name')}\" from {args.get('entity_type')}"


def _narrate_categorize_alert(args: dict, mode: str) -> str:
    cat = args.get("category") or "a category"
    tier = args.get("urgency_tier")
    suffix = f" ({tier})" if tier else ""
    if mode == "suggest":
        return f"Suggests categorizing this alert as {cat}{suffix} — awaiting approval"
    return f"Categorized this alert as {cat}{suffix}"


def _narrate_escalate(args: dict) -> str:
    summary = (args.get("summary") or args.get("reason") or "needs your attention").strip()
    return f"Escalated to operator: {summary}"


def _narrate_mark_bad_actor(args: dict, mode: str) -> str:
    phone = _short_phone(args.get("phone"))
    if mode == "suggest":
        return f"Suggests flagging {phone} as a bad actor — awaiting approval"
    return f"Flagged {phone} as a bad actor"


def _narrate_update_alert_status(args: dict, mode: str) -> str:
    status = args.get("status") or "a new status"
    if mode == "suggest":
        return f"Suggests setting alert status to {status} — awaiting approval"
    return f"Set alert status to {status}"


def _narrate_noop(args: dict) -> str:
    reason = args.get("reason") or "no action"
    return f"Reviewed the bucket — {reason}"


_DISPATCH = {
    "send": lambda args, mode: _narrate_send(args, mode),
    "record_sighting": lambda args, _mode: _narrate_record_sighting(args),
    "upsert_cluster": lambda args, _mode: _narrate_upsert_cluster(args),
    "merge_clusters": lambda args, _mode: _narrate_merge_clusters(args),
    "upsert_trajectory": lambda args, _mode: _narrate_upsert_trajectory(args),
    "apply_tag": lambda args, _mode: _narrate_apply_tag(args),
    "remove_tag": lambda args, _mode: _narrate_remove_tag(args),
    "categorize_alert": lambda args, mode: _narrate_categorize_alert(args, mode),
    "escalate_to_ngo": lambda args, _mode: _narrate_escalate(args),
    "mark_bad_actor": lambda args, mode: _narrate_mark_bad_actor(args, mode),
    "update_alert_status": lambda args, mode: _narrate_update_alert_status(args, mode),
    "noop": lambda args, _mode: _narrate_noop(args),
}


def narrate_call(name: str, args: dict, mode: str) -> str:
    """Narrate a single tool call as one verb-led sentence."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"Performed {name}"
    return fn(args, mode)


def narrate_decision(
    staged_calls: list[Any],
    alert: Any = None,
    is_heartbeat: bool = False,
) -> str:
    """Compose one sentence describing the whole decision.

    `staged_calls` is a list of objects each having `.tool_name`, `.args`,
    `.mode` (typically StagedToolCall instances or dict-like with the same
    keys). `alert` is optional; we use it to mention the case subject when
    helpful.
    """
    def _g(call: Any, attr: str, default: Any = None) -> Any:
        if isinstance(call, dict):
            return call.get(attr, default)
        return getattr(call, attr, default)

    if not staged_calls:
        if is_heartbeat:
            return "Heartbeat: reviewed the case, no new action needed"
        return "Reviewed the bucket, no action taken"

    parts = [
        narrate_call(_g(c, "tool_name", ""), _g(c, "args", {}) or {}, _g(c, "mode", "execute"))
        for c in staged_calls
    ]

    # If multiple calls collapse the most informative two into one sentence
    # ("X and Y"); drop noop if it appears alongside real actions.
    real = [p for p in parts if not p.startswith("Reviewed the bucket")]
    if not real:
        sentence = parts[0]
    elif len(real) == 1:
        sentence = real[0]
    elif len(real) == 2:
        sentence = f"{real[0]} and {real[1].lower()}"
    else:
        sentence = real[0] + f" (+{len(real) - 1} more action{'s' if len(real) > 2 else ''})"

    # Append case subject when the alert is set and not already mentioned.
    if alert is not None:
        person = (
            getattr(alert, "person_name", None)
            or (alert.get("person_name") if isinstance(alert, dict) else None)
            or (alert.get("personName") if isinstance(alert, dict) else None)
        )
        if person and person.lower() not in sentence.lower():
            sentence = f"{sentence} — for {person}"

    return _truncate(sentence)
