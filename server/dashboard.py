"""Insight aggregation for the operator Dashboard.

Heuristic-only — the routing agent does message-level classification upstream;
this module aggregates *across cases* per region to surface trends and
suggest broadcasts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from . import audiences as audiences_module
from .schemas import Message, Region
from .store import store


# Map of need keywords -> recommended audience id
NEED_TO_AUDIENCE: dict[str, str] = {
    "insulin": "doctors_near_sanaa",
    "medicine": "doctors_global",
    "medical": "doctors_global",
    "water": "ngo_field_staff",
    "food": "ngo_field_staff",
    "baby formula": "ngo_field_staff",
    "shelter": "ngo_field_staff",
    "adult escort": "ngo_field_staff",
}

# message theme → human label and default broadcast verb
THEME_LABELS = {
    "missing_person": ("Missing person", "Send Amber Alert"),
    "water": ("Water shortage", "Request water delivery"),
    "food": ("Food shortage", "Request food delivery"),
    "insulin": ("Insulin / medical", "Request doctors"),
    "medicine": ("Medical supplies", "Request doctors"),
    "shelter": ("Shelter needed", "Request NGO support"),
}


def _compute_urgency(
    anomaly: bool,
    msgs_per_min: float,
    baseline: float,
    distress: int,
    open_cases: int,
    distinct_senders: int,
    has_critical_case: bool,
    has_high_case: bool,
) -> int:
    score = 0.0
    score += 25.0 if anomaly else 0.0
    if baseline >= 0.05:
        score += 15.0 * min(1.0, msgs_per_min / max(1.0, 5.0 * baseline))
    score += 25.0 * min(1.0, distress / 6.0)
    score += 20.0 * min(1.0, open_cases / 3.0)
    score += 10.0 * min(1.0, distinct_senders / 8.0)
    # severity boost — a critical open case dominates
    if has_critical_case:
        score += 35.0
    elif has_high_case:
        score += 15.0
    return max(0, min(100, round(score)))


def _detect_themes(messages: list[Message]) -> list[dict[str, Any]]:
    """Return ranked themes for a region's recent messages."""
    need_counts: Counter[str] = Counter()
    locations_per_need: dict[str, set[str]] = defaultdict(set)
    senders_per_need: dict[str, set[str]] = defaultdict(set)
    msg_ids_per_need: dict[str, list[str]] = defaultdict(list)
    distress_per_need: dict[str, int] = defaultdict(int)

    for m in messages:
        if not m.extracted:
            continue
        needs = [n.lower() for n in (m.extracted.needs or [])]
        loc = (m.extracted.location or "").strip()
        for need in needs:
            need_counts[need] += 1
            if loc:
                locations_per_need[need].add(loc)
            senders_per_need[need].add(m.sender)
            msg_ids_per_need[need].append(m.messageId)
            if m.extracted.distress:
                distress_per_need[need] += 1

    themes: list[dict[str, Any]] = []
    for need, count in need_counts.most_common():
        # generic "label" fallback if not in map
        label, action = THEME_LABELS.get(
            need, (need.capitalize(), f"Request help: {need}")
        )
        suggested_audience_id = NEED_TO_AUDIENCE.get(need)
        # tighten audience if locations cluster
        themes.append(
            {
                "need": need,
                "label": label,
                "action": action,
                "count": count,
                "distinctSenders": len(senders_per_need[need]),
                "distressCount": distress_per_need[need],
                "locations": sorted(locations_per_need[need])[:3],
                "suggestedAudienceId": suggested_audience_id,
                "messageIds": msg_ids_per_need[need][:5],
            }
        )

    return themes


def _missing_person_theme(open_cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """If there are open missing-person cases in the region, surface them."""
    mp = [c for c in open_cases if c["category"] == "missing_person"]
    if not mp:
        return None
    return {
        "need": "missing_person",
        "label": THEME_LABELS["missing_person"][0],
        "action": THEME_LABELS["missing_person"][1],
        "count": sum(c["messageCount"] for c in mp),
        "distinctSenders": 0,
        "distressCount": 0,
        "locations": [c["title"] for c in mp[:3]],
        "suggestedAudienceId": None,  # Civilians-in-region picked client-side
        "messageIds": [],
        "incidentIds": [c["id"] for c in mp],
    }


def build_dashboard(window_minutes: int = 60) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    incidents = store.list_incidents()

    region_payloads: list[dict[str, Any]] = []
    recent_distress: list[dict[str, Any]] = []

    for region_id, meta in audiences_module.REGION_META.items():
        in_region = [i for i in incidents if i.region == region_id]
        # all messages from all incidents in this region (cap to window for trend detection)
        all_msgs: list[Message] = []
        for inc in in_region:
            all_msgs.extend(store.list_messages(inc.id))

        recent = [m for m in all_msgs if m.ts >= cutoff and not m.outbound]
        # if the demo has no recent traffic, fall back to last N inbound messages
        # so themes still surface in seeded state
        if not recent:
            inbound = [m for m in all_msgs if not m.outbound]
            recent = sorted(inbound, key=lambda m: m.ts, reverse=True)[:30]

        distress_count = sum(
            1 for m in recent if m.extracted and m.extracted.distress
        )
        distinct_senders = len({m.sender for m in recent})

        msgs_per_min = store.msgs_per_minute(region_id)
        baseline = store.baseline_msgs_per_minute(region_id)
        anomaly = msgs_per_min > 3 * baseline + 2

        case_summary = [
            {
                "id": i.id,
                "title": i.title,
                "category": i.category,
                "severity": i.severity,
                "messageCount": i.messageCount,
            }
            for i in in_region
        ]

        themes = _detect_themes(recent)
        mp_theme = _missing_person_theme(case_summary)
        if mp_theme:
            themes = [mp_theme] + themes
        # only keep themes with at least 1 reporter or that are missing-person
        themes = [
            t for t in themes if t["distinctSenders"] >= 1 or t["need"] == "missing_person"
        ][:4]

        urgency = _compute_urgency(
            anomaly=anomaly,
            msgs_per_min=msgs_per_min,
            baseline=baseline,
            distress=distress_count,
            open_cases=len(in_region),
            distinct_senders=distinct_senders,
            has_critical_case=any(c["severity"] == "critical" for c in case_summary),
            has_high_case=any(c["severity"] == "high" for c in case_summary),
        )

        # 60-minute timeline buckets (count per minute) for the sparkline
        timeline = store.timeline(region_id, minutes=60, bucket_seconds=60)
        spark = [c for _, c in timeline]

        region_payloads.append(
            {
                "region": region_id,
                "label": meta["label"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "urgency": urgency,
                "anomaly": anomaly,
                "msgsPerMin": round(msgs_per_min, 2),
                "baselineMsgsPerMin": round(baseline, 2),
                "openCases": len(in_region),
                "messageCount": len(recent),
                "distressCount": distress_count,
                "distinctSenders": distinct_senders,
                "sparkline": spark,
                "themes": themes,
                "cases": case_summary,
            }
        )

        for m in recent:
            if m.extracted and m.extracted.distress:
                recent_distress.append(
                    {
                        "messageId": m.messageId,
                        "incidentId": m.incidentId,
                        "region": region_id,
                        "regionLabel": meta["label"],
                        "from": m.sender,
                        "body": m.body,
                        "ts": m.ts.isoformat(),
                    }
                )

    region_payloads.sort(key=lambda r: r["urgency"], reverse=True)
    recent_distress.sort(key=lambda r: r["ts"], reverse=True)

    return {
        "windowMinutes": window_minutes,
        "regions": region_payloads,
        "recentDistress": recent_distress[:6],
    }
