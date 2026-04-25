"""Rich demo seeder.

Creates a populated multi-region scene so the dashboard opens *alive*:
8 alerts across 6 regions, ~40 accounts, ~60 historic inbound messages
already triaged into Buckets, ~30 Sightings, 4 SightingClusters, 2
Trajectories, ~15 historic AgentDecisions with realistic reasoning, and a
mix of ToolCalls — some auto-executed (audit trail), several pending
(operator approvals inbox).

Idempotent: a second call returns counts and changes nothing. Pass
`reset=True` to wipe Warchild and re-seed from scratch.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.registry import REGIONS
from server.db.alerts import Alert, AlertDelivery
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO, Account
from server.db.knowledge import SightingCluster, Tag, TagAssignment, Trajectory
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import OutboundMessage, Sighting
from server.db.trust import BadActor

NGO_NAME = "Warchild"


# ---------------------------------------------------------------------------
# Static demo content
# ---------------------------------------------------------------------------


_ACCOUNT_NAMES_BY_REGION: dict[str, list[tuple[str, str]]] = {
    # (phone, language)
    "IRQ_BAGHDAD": [
        ("+9647000000001", "ar"), ("+9647000000010", "ar"),
        ("+9647000000011", "ar"), ("+9647000000012", "ar"),
        ("+9647000000013", "en"), ("+9647000000014", "ar"),
        ("+9647000000015", "ar"),
    ],
    "IRQ_MOSUL": [
        ("+9647000000002", "ar"), ("+9647000000020", "ar"),
        ("+9647000000021", "ar"), ("+9647000000022", "en"),
        ("+9647000000023", "ar"),
    ],
    "SYR_ALEPPO": [
        ("+9639000000001", "ar"), ("+9639000000010", "ar"),
        ("+9639000000011", "ar"), ("+9639000000012", "ar"),
        ("+9639000000013", "en"), ("+9639000000014", "ar"),
    ],
    "SYR_DAMASCUS": [
        ("+9639000000002", "ar"), ("+9639000000020", "ar"),
        ("+9639000000021", "ar"), ("+9639000000022", "ar"),
    ],
    "YEM_SANAA": [
        ("+9677000000001", "ar"), ("+9677000000010", "ar"),
        ("+9677000000011", "ar"), ("+9677000000012", "en"),
        ("+9677000000013", "ar"), ("+9677000000014", "ar"),
    ],
    "LBN_BEIRUT": [
        ("+9613000000001", "ar"), ("+9613000000010", "ar"),
        ("+9613000000011", "en"), ("+9613000000012", "ar"),
    ],
}


_BAD_ACTOR_PHONES = ["+9647777666555", "+9639888777666"]


# Each tuple: (region_key, person_name, description, category, urgency_tier,
#             urgency_score, status, age_minutes_ago)
_ALERTS: list[tuple[str, str, str, str, str, float, str, int]] = [
    ("IRQ_BAGHDAD", "Amira Hassan",
     "8-year-old girl, last seen near Al-Shorja market wearing a red dress.",
     "missing_person", "high", 0.86, "active", 95),
    ("IRQ_BAGHDAD", "Ibrahim Najjar",
     "Insulin urgently needed at Al-Karkh district pharmacy for diabetic patient.",
     "medical", "medium", 0.62, "active", 38),
    ("IRQ_MOSUL", "Hassan al-Bayati",
     "72-year-old man with dementia missing from Bab al-Tob neighborhood since dawn.",
     "missing_person", "medium", 0.58, "active", 220),
    ("SYR_ALEPPO", "Bustan al-Qasr collapse",
     "Building collapse reported in Bustan al-Qasr — residents trapped, need rescue coordination.",
     "safety", "critical", 0.94, "active", 18),
    ("SYR_DAMASCUS", "Eastern Ghouta water shortage",
     "Multiple households reporting no running water for 48 hours in eastern Ghouta.",
     "resource_shortage", "low", 0.32, "active", 700),
    ("YEM_SANAA", "Layla Saeed",
     "11-year-old girl, separated from family at Bab al-Yemen souk this morning.",
     "missing_person", "high", 0.81, "active", 60),
    ("YEM_SANAA", "Fuel shortage Sanaa north",
     "Generator fuel running out at neighborhood clinic, ICU equipment at risk.",
     "medical", "high", 0.78, "active", 130),
    ("LBN_BEIRUT", "Karim Mansour",
     "Elderly man missing from Hamra district, has heart condition.",
     "missing_person", "medium", 0.55, "active", 410),
]


# Inbound message templates per region (mix of sighting/question/ack/noise).
# Each entry: (classification, language, body, geohash6_suffix, confidence)
_INBOUND_BY_REGION: dict[str, list[tuple[str, str, str, str, float]]] = {
    "IRQ_BAGHDAD": [
        ("sighting", "ar", "رأيت طفلة بفستان أحمر بالقرب من المخبز قبل عشر دقائق", "u0", 0.82),
        ("sighting", "ar", "بنت صغيرة وحدها على شارع الرشيد، تبكي", "u1", 0.76),
        ("sighting", "en", "Saw a girl matching the description near Al-Mutanabbi street", "u2", 0.71),
        ("sighting", "ar", "طفلة بفستان أحمر تتجه نحو الجسر", "u0", 0.78),
        ("question", "ar", "هل ما زالت الفتاة مفقودة؟ نسمع أصوات بعيدة", "u3", 0.40),
        ("ack", "ar", "تم البحث في حيي ولم نرها", "u4", 0.50),
        ("sighting", "ar", "شخص رآها بالقرب من سوق الخضار قبل ربع ساعة", "u1", 0.72),
        ("noise", "ar", "السلام عليكم", "u5", 0.10),
        ("sighting", "en", "Two witnesses say a girl in red was put in a white car near checkpoint", "u2", 0.88),
        ("sighting", "ar", "وجدنا فستاناً أحمر بالقرب من النهر، نحقق الآن", "u0", 0.84),
        ("ack", "ar", "نحن نراقب نقطة التفتيش", "u3", 0.55),
        ("sighting", "ar", "الطفلة تجلس على رصيف بالقرب من المسجد، نطمئنها", "u1", 0.91),
        # Medical alert messages
        ("question", "ar", "هل توجد صيدلية مفتوحة لديها أنسولين؟", "u4", 0.50),
        ("ack", "en", "I have insulin pens, can deliver to Al-Karkh in 30min", "u3", 0.85),
        ("sighting", "ar", "صيدلية الرشيد لديها مخزون", "u2", 0.74),
    ],
    "IRQ_MOSUL": [
        ("sighting", "ar", "رجل مسن يقف وحيداً قرب بوابة المدينة", "p0", 0.69),
        ("sighting", "en", "Elderly man wandering near the old market, looks confused", "p1", 0.74),
        ("sighting", "ar", "أعتقد أنني رأيته يدخل المسجد القديم", "p2", 0.62),
        ("question", "ar", "ما اسمه ومن يبحث عنه؟", "p3", 0.40),
        ("ack", "ar", "أبلغنا الإمام، سيراقب الأمر", "p2", 0.55),
        ("sighting", "ar", "وجدت رجلاً مسناً جالساً على المقهى، أعتقد أنه هو", "p1", 0.81),
    ],
    "SYR_ALEPPO": [
        ("sighting", "ar", "سقط مبنى بستان القصر، نسمع صراخاً من تحت الأنقاض", "q0", 0.93),
        ("sighting", "ar", "أحتاج معدات حفر، عائلتان محاصرتان", "q1", 0.91),
        ("sighting", "en", "Civil defense team on site, requesting backup", "q2", 0.87),
        ("question", "ar", "كم عدد المفقودين؟", "q0", 0.50),
        ("sighting", "ar", "أخرجنا طفلين، نواصل العمل", "q0", 0.88),
        ("ack", "en", "Hospital alerted, sending ambulances", "q3", 0.85),
        ("noise", "ar", "الله أكبر", "q4", 0.20),
        ("sighting", "ar", "مهندس مدني هنا، الجدار الجنوبي غير مستقر، نحتاج إخلاء", "q1", 0.92),
    ],
    "SYR_DAMASCUS": [
        ("question", "ar", "متى ستعود المياه؟", "t0", 0.40),
        ("question", "ar", "هل توجد صهاريج توزيع قريبة؟", "t1", 0.42),
        ("ack", "ar", "البلدية أبلغتنا أنها تعمل على الإصلاح", "t2", 0.55),
        ("sighting", "ar", "صهريج وصل إلى الحي ولكن يكفي ٢٠ بيت فقط", "t1", 0.68),
    ],
    "YEM_SANAA": [
        ("sighting", "ar", "بنت صغيرة بحجاب أزرق تبكي قرب باب اليمن", "w0", 0.84),
        ("sighting", "ar", "رأيتها مع امرأة لا أعرفها، اتجهتا غرباً", "w1", 0.79),
        ("sighting", "en", "Found a child matching the description near the spice market", "w2", 0.86),
        ("question", "ar", "ما عمر الطفلة بالضبط؟", "w0", 0.40),
        ("ack", "ar", "أبلغت أهلي ليبحثوا في السوق", "w1", 0.55),
        ("sighting", "ar", "الطفلة الآن في متجر التوابل، صاحب المتجر يطعمها", "w2", 0.93),
        # Fuel shortage
        ("ack", "ar", "لدينا برميل وقود إضافي، نوصله الآن", "w3", 0.82),
    ],
    "LBN_BEIRUT": [
        ("sighting", "ar", "رجل مسن جالس على رصيف الحمرا، يبدو تائهاً", "j0", 0.71),
        ("sighting", "en", "Elderly gentleman near AUB gate asking for directions", "j1", 0.78),
        ("question", "ar", "هل أحضر له ماءً وكرسياً؟", "j0", 0.50),
        ("ack", "ar", "صيدلية الحمرا أبلغت، ستراقب", "j1", 0.55),
    ],
}


def _now() -> datetime:
    return datetime.now(UTC)


def _ago(minutes: float) -> datetime:
    return _now() - timedelta(minutes=minutes)


def _idem(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def _hash_to_vec(text: str) -> list[float]:
    """Deterministic 512-float embedding (matches triage_client.hash_to_vec)."""
    seed = text.encode("utf-8")
    floats: list[float] = []
    i = 0
    while len(floats) < 512:
        d = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        for b in d:
            floats.append((b / 127.5) - 1.0)
            if len(floats) == 512:
                break
        i += 1
    return floats


# ---------------------------------------------------------------------------
# Idempotency / reset
# ---------------------------------------------------------------------------


async def _wipe_warchild(db: AsyncSession) -> None:
    """Delete the Warchild NGO and all its dependents in FK-safe order."""
    ngo_ids = (
        await db.execute(select(NGO.ngo_id).where(NGO.name == NGO_NAME))
    ).scalars().all()
    if not ngo_ids:
        return

    alert_ids = (
        await db.execute(select(Alert.alert_id).where(Alert.ngo_id.in_(ngo_ids)))
    ).scalars().all()

    # ToolCall + AgentDecision + OutboundMessage chain
    bucket_keys = (
        await db.execute(select(Bucket.bucket_key).where(Bucket.ngo_id.in_(ngo_ids)))
    ).scalars().all()
    decision_ids = (
        await db.execute(
            select(AgentDecision.decision_id).where(AgentDecision.ngo_id.in_(ngo_ids))
        )
    ).scalars().all()
    tc_ids = (
        await db.execute(select(ToolCall.call_id).where(ToolCall.ngo_id.in_(ngo_ids)))
    ).scalars().all()
    if tc_ids:
        await db.execute(
            delete(OutboundMessage).where(OutboundMessage.tool_call_id.in_(tc_ids))
        )
        await db.execute(delete(ToolCall).where(ToolCall.call_id.in_(tc_ids)))
    if decision_ids:
        await db.execute(
            delete(AgentDecision).where(AgentDecision.decision_id.in_(decision_ids))
        )

    # Knowledge artifacts
    if alert_ids:
        await db.execute(
            delete(TagAssignment).where(TagAssignment.alert_id.in_(alert_ids))
        )
        await db.execute(delete(SightingCluster).where(SightingCluster.alert_id.in_(alert_ids)))
        await db.execute(delete(Trajectory).where(Trajectory.alert_id.in_(alert_ids)))
        await db.execute(delete(Sighting).where(Sighting.alert_id.in_(alert_ids)))
    await db.execute(delete(Tag).where(Tag.ngo_id.in_(ngo_ids)))

    # Messages
    if alert_ids:
        msg_ids = (
            await db.execute(
                select(InboundMessage.msg_id).where(
                    InboundMessage.in_reply_to_alert_id.in_(alert_ids)
                )
            )
        ).scalars().all()
        if msg_ids:
            await db.execute(
                delete(TriagedMessage).where(TriagedMessage.msg_id.in_(msg_ids))
            )
            await db.execute(
                delete(InboundMessage).where(InboundMessage.msg_id.in_(msg_ids))
            )
    if bucket_keys:
        await db.execute(delete(Bucket).where(Bucket.bucket_key.in_(bucket_keys)))

    if alert_ids:
        await db.execute(delete(AlertDelivery).where(AlertDelivery.alert_id.in_(alert_ids)))
        await db.execute(delete(Alert).where(Alert.alert_id.in_(alert_ids)))

    await db.execute(delete(BadActor).where(BadActor.ngo_id.in_(ngo_ids)))
    await db.execute(delete(Account).where(Account.ngo_id.in_(ngo_ids)))
    await db.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
    await db.commit()


async def _existing_summary(db: AsyncSession) -> dict[str, Any] | None:
    """Return current row counts if Warchild already seeded; else None."""
    ngo = (
        await db.execute(select(NGO).where(NGO.name == NGO_NAME))
    ).scalar_one_or_none()
    if ngo is None:
        return None
    alerts = (
        await db.execute(select(Alert).where(Alert.ngo_id == ngo.ngo_id))
    ).scalars().all()
    accounts = (
        await db.execute(select(Account).where(Account.ngo_id == ngo.ngo_id))
    ).scalars().all()
    inbound = (
        await db.execute(
            select(InboundMessage).where(InboundMessage.ngo_id == ngo.ngo_id)
        )
    ).scalars().all()
    sightings = (
        await db.execute(select(Sighting).where(Sighting.ngo_id == ngo.ngo_id))
    ).scalars().all()
    decisions = (
        await db.execute(select(AgentDecision).where(AgentDecision.ngo_id == ngo.ngo_id))
    ).scalars().all()
    pending = (
        await db.execute(
            select(ToolCall).where(
                ToolCall.ngo_id == ngo.ngo_id,
                ToolCall.approval_status == "pending",
            )
        )
    ).scalars().all()
    return {
        "ok": True,
        "ngo_id": ngo.ngo_id,
        "alert_id": alerts[0].alert_id if alerts else "",
        "seeded": {
            "accounts": len(accounts),
            "alerts": len(alerts),
            "inbound_messages": len(inbound),
            "sightings": len(sightings),
            "agent_decisions": len(decisions),
            "pending_suggestions": len(pending),
        },
        "alreadyExisted": True,
    }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


async def _create_ngo_and_accounts(db: AsyncSession) -> tuple[NGO, dict[str, list[Account]]]:
    ngo = NGO(
        name=NGO_NAME,
        region_geohash_prefix="sv",
        standing_orders=(
            "Auto-broadcast missing-child sightings within 100m geohash to "
            "verified eyewitnesses (audience<=200). Route any send to "
            "all_alert/all_ngo to operator for approval. Mark phones as "
            "bad actors only on operator confirmation."
        ),
    )
    db.add(ngo)
    await db.flush()

    by_region: dict[str, list[Account]] = {}
    for region_key, entries in _ACCOUNT_NAMES_BY_REGION.items():
        prefix = REGIONS[region_key]["geohash_prefix"]
        accounts: list[Account] = []
        for idx, (phone, language) in enumerate(entries):
            acc = Account(
                phone=phone,
                ngo_id=ngo.ngo_id,
                language=language,
                home_geohash=prefix + ("u" if idx % 2 == 0 else "1"),
                last_known_geohash=prefix + chr(ord("0") + idx % 6),
                trust_score=0.6 + (idx % 4) * 0.1,
                source="app" if idx % 3 != 0 else "seed",
            )
            db.add(acc)
            accounts.append(acc)
        by_region[region_key] = accounts
    await db.flush()
    return ngo, by_region


async def _create_alerts(
    db: AsyncSession, ngo: NGO, accounts_by_region: dict[str, list[Account]]
) -> list[Alert]:
    alerts: list[Alert] = []
    for region_key, person_name, desc, category, tier, score, status, age_min in _ALERTS:
        meta = REGIONS[region_key]
        alert = Alert(
            ngo_id=ngo.ngo_id,
            person_name=person_name,
            description=desc,
            last_seen_geohash=meta["geohash_prefix"] + "u0",
            region_geohash_prefix=meta["geohash_prefix"],
            status=status,
            category=category,
            urgency_tier=tier,
            urgency_score=score,
            expires_at=_now() + timedelta(days=2),
        )
        # Backdate created_at via SQL would be ideal; for demo, rely on natural ordering
        db.add(alert)
        await db.flush()

        # AlertDelivery to every account in the region.
        for acc in accounts_by_region.get(region_key, []):
            db.add(AlertDelivery(
                ngo_id=ngo.ngo_id, alert_id=alert.alert_id, recipient_phone=acc.phone,
            ))
        alerts.append(alert)
    await db.flush()
    return alerts


def _bucket_for(alert: Alert, ago_min: int, ngo_id: str) -> Bucket:
    prefix = (alert.region_geohash_prefix or "unkn")[:4]
    ts = _ago(ago_min).replace(microsecond=0)
    return Bucket(
        bucket_key=f"{alert.alert_id}|{prefix}|{ts.isoformat()}",
        ngo_id=ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4=prefix,
        window_start=ts,
        window_length_ms=3000,
        status="done",
    )


async def _seed_messages_buckets_and_triage(
    db: AsyncSession,
    ngo: NGO,
    alerts: list[Alert],
    accounts_by_region: dict[str, list[Account]],
) -> dict[str, list[Bucket]]:
    """For each alert, create inbound + triaged + 1-2 done buckets covering them.

    Returns a map alert_id -> [buckets] so AgentDecisions can link.
    """
    by_alert: dict[str, list[Bucket]] = {}
    rng = random.Random(42)

    for alert in alerts:
        region_key = next(
            (rk for rk, m in REGIONS.items() if m["geohash_prefix"] == alert.region_geohash_prefix),
            "IRQ_BAGHDAD",
        )
        templates = _INBOUND_BY_REGION.get(region_key, [])
        if not templates:
            continue
        accs = accounts_by_region.get(region_key, [])
        if not accs:
            continue

        # Distribute messages across 2 historic buckets per alert
        bucket1 = _bucket_for(alert, ago_min=45, ngo_id=ngo.ngo_id)
        bucket2 = _bucket_for(alert, ago_min=15, ngo_id=ngo.ngo_id)
        db.add_all([bucket1, bucket2])
        await db.flush()
        by_alert[alert.alert_id] = [bucket1, bucket2]

        for i, (cls, lang, body, gh_suffix, conf) in enumerate(templates):
            sender = accs[i % len(accs)]
            received = _ago(60 - i * 3 + rng.randint(-2, 2))
            inbound = InboundMessage(
                ngo_id=ngo.ngo_id,
                channel="sms" if i % 3 == 0 else "app",
                sender_phone=sender.phone,
                in_reply_to_alert_id=alert.alert_id,
                body=body,
                media_urls=[],
                raw={"seeded": True},
                received_at=received,
                status="triaged",
            )
            db.add(inbound)
            await db.flush()

            bucket = bucket1 if i < len(templates) // 2 else bucket2
            triaged = TriagedMessage(
                msg_id=inbound.msg_id,
                ngo_id=ngo.ngo_id,
                classification=cls,
                geohash6=(alert.region_geohash_prefix or "") + gh_suffix,
                geohash_source="body_extraction",
                confidence=conf,
                language=lang,
                bucket_key=bucket.bucket_key,
                body_embedding=_hash_to_vec(body),
            )
            db.add(triaged)
        await db.flush()
    return by_alert


async def _seed_sightings(db: AsyncSession, ngo: NGO, alerts: list[Alert]) -> list[Sighting]:
    """Pre-create Sightings tied to the missing-person/safety alerts."""
    sightings: list[Sighting] = []
    for alert in alerts:
        if alert.category not in ("missing_person", "safety"):
            continue
        region_prefix = alert.region_geohash_prefix or "sv8d"
        # 4 sightings per qualifying alert
        for k in range(4):
            note = (
                f"Confirmed sighting near landmark #{k+1}; matches description. "
                f"Witness reports subject was moving "
                f"{'south' if k % 2 == 0 else 'east'}-bound."
            )
            s = Sighting(
                ngo_id=ngo.ngo_id,
                alert_id=alert.alert_id,
                observer_phone=f"+9647777{1000 + k}",
                geohash=region_prefix + chr(ord("u") + (k % 4)) + str(k),
                notes=note,
                confidence=0.62 + 0.07 * k,
                photo_urls=[],
                notes_embedding=_hash_to_vec(note),
            )
            db.add(s)
            sightings.append(s)
    await db.flush()
    return sightings


async def _seed_clusters_and_trajectory(
    db: AsyncSession, ngo: NGO, alerts: list[Alert], sightings: list[Sighting]
) -> tuple[list[SightingCluster], list[Trajectory]]:
    """4 active clusters + 2 trajectories for the most-tracked alerts."""
    clusters: list[SightingCluster] = []
    trajectories: list[Trajectory] = []

    by_alert: dict[str, list[Sighting]] = {}
    for s in sightings:
        by_alert.setdefault(s.alert_id, []).append(s)

    flagship_alerts = [a for a in alerts if a.category == "missing_person"][:4]
    cluster_labels = ["Bakery sightings", "Market vicinity",
                      "Old town corridor", "Riverside path"]

    for idx, alert in enumerate(flagship_alerts):
        members = by_alert.get(alert.alert_id, [])[:3]
        if not members:
            continue
        cluster = SightingCluster(
            ngo_id=ngo.ngo_id,
            alert_id=alert.alert_id,
            label=cluster_labels[idx % len(cluster_labels)],
            center_geohash=members[0].geohash,
            radius_m=120 + idx * 30,
            time_window_start=_ago(60),
            time_window_end=_now(),
            sighting_ids=[m.sighting_id for m in members],
            sighting_count=len(members),
            mean_confidence=sum(m.confidence for m in members) / len(members),
            status="active",
            last_member_added_at=_ago(8 + idx * 2),
            embedding=_hash_to_vec(cluster_labels[idx % len(cluster_labels)]),
        )
        db.add(cluster)
        clusters.append(cluster)

    # 2 active trajectories on the first two flagship alerts
    for idx, alert in enumerate(flagship_alerts[:2]):
        members = by_alert.get(alert.alert_id, [])[:3]
        if not members:
            continue
        points = [
            {"geohash": m.geohash, "t": _ago(50 - i * 15).isoformat(),
             "sighting_ids": [m.sighting_id]}
            for i, m in enumerate(members)
        ]
        trajectories.append(Trajectory(
            ngo_id=ngo.ngo_id,
            alert_id=alert.alert_id,
            points=points,
            direction_deg=210.0 + idx * 30,
            speed_kmh=4.5,
            confidence=0.72,
            status="active",
            last_extended_at=_ago(7),
        ))
    db.add_all(trajectories)

    await db.flush()
    return clusters, trajectories


async def _seed_decisions_and_toolcalls(
    db: AsyncSession,
    ngo: NGO,
    alerts: list[Alert],
    buckets_by_alert: dict[str, list[Bucket]],
    sightings: list[Sighting],
) -> tuple[list[AgentDecision], list[ToolCall]]:
    """Create historic AgentDecisions + ToolCalls.

    Mix of: auto-executed action, pending suggestions (the inbox), and noop
    heartbeats. Reasoning summaries are realistic English so the activity
    tape reads well.
    """
    decisions: list[AgentDecision] = []
    tool_calls: list[ToolCall] = []

    by_alert_sightings: dict[str, list[Sighting]] = {}
    for s in sightings:
        by_alert_sightings.setdefault(s.alert_id, []).append(s)

    summaries_per_alert: dict[str, list[tuple[str, str, list[dict]]]] = {
        # alert_id_marker -> [(reasoning, kind, [tool_call_specs])]
        # kind: 'execute_pair' | 'suggest_broadcast' | 'noop' | 'escalate'
    }

    decision_recipes: list[tuple[str, str, str, list[dict]]] = []

    for alert in alerts:
        buckets = buckets_by_alert.get(alert.alert_id) or []
        if not buckets:
            continue

        # Recipe: 2 historic execute decisions + 1 pending suggest
        if alert.category in ("missing_person", "safety"):
            decision_recipes.append((
                alert.alert_id, buckets[0].bucket_key,
                "Two sightings near central landmark; recorded both and acked observers.",
                [
                    {"tool_name": "record_sighting", "mode": "execute",
                     "approval_status": "auto_executed",
                     "args": {"alert_id": alert.alert_id,
                              "observer_phone": "+9647000000010",
                              "geohash": (alert.region_geohash_prefix or "sv8d") + "u0",
                              "notes": "Sighting near landmark — corroborated.",
                              "confidence": 0.78, "photo_urls": []}},
                    {"tool_name": "send", "mode": "execute",
                     "approval_status": "auto_executed",
                     "args": {"audience": {"type": "one", "phone": "+9647000000010"},
                              "bodies": {"en": "Thanks — your sighting is logged."},
                              "mode": "execute"}},
                ],
            ))
            decision_recipes.append((
                alert.alert_id, buckets[1].bucket_key,
                "Cluster forming near bakery; suggesting broadcast to 1,540 verified eyewitnesses.",
                [
                    {"tool_name": "send", "mode": "suggest",
                     "approval_status": "pending",
                     "args": {"audience": {"type": "audience_id",
                                           "id": "verified_eyewitnesses"},
                              "bodies": {"en": (
                                  f"Update on {alert.person_name}: cluster of "
                                  "sightings near central market. If you are in "
                                  "the area, please report any matching person."
                              )},
                              "mode": "suggest", "incident_id": alert.alert_id}},
                ],
            ))
        elif alert.category == "medical":
            decision_recipes.append((
                alert.alert_id, buckets[0].bucket_key,
                "Insulin offers received from two responders; coordinating handoff.",
                [
                    {"tool_name": "record_sighting", "mode": "execute",
                     "approval_status": "auto_executed",
                     "args": {"alert_id": alert.alert_id,
                              "observer_phone": "+9647000000013",
                              "geohash": (alert.region_geohash_prefix or "sv8d") + "u3",
                              "notes": "Pharmacy reports insulin in stock.",
                              "confidence": 0.81, "photo_urls": []}},
                    {"tool_name": "send", "mode": "suggest",
                     "approval_status": "pending",
                     "args": {"audience": {"type": "audience_id",
                                           "id": "medical_responders"},
                              "bodies": {"en": (
                                  "Coordinate insulin handoff at Al-Karkh "
                                  "pharmacy. Patient needs supply in next 2 hours."
                              )},
                              "mode": "suggest", "incident_id": alert.alert_id}},
                ],
            ))
        elif alert.category == "resource_shortage":
            decision_recipes.append((
                alert.alert_id, buckets[0].bucket_key,
                "Heartbeat: water situation unchanged in last 60 min — monitoring.",
                [
                    {"tool_name": "noop", "mode": "execute",
                     "approval_status": "auto_executed",
                     "args": {"reason": "no new actionable inbound"}},
                ],
            ))

    # Add a couple of operator-flavored special decisions: escalations + categorize_alert pending
    flagship = next((a for a in alerts if a.category == "missing_person"), None)
    if flagship and buckets_by_alert.get(flagship.alert_id):
        # Dedicated bucket for the escalation so we don't collide with the
        # other decisions on the same flagship bucket (UNIQUE(bucket_key)).
        escalation_bucket = _bucket_for(flagship, ago_min=5, ngo_id=ngo.ngo_id)
        db.add(escalation_bucket)
        await db.flush()
        decision_recipes.append((
            flagship.alert_id,
            escalation_bucket.bucket_key,
            "Conflicting sightings 4km apart in same window — escalating to operator.",
            [
                {"tool_name": "escalate_to_ngo", "mode": "execute",
                 "approval_status": "auto_executed",
                 "args": {"reason": "conflicting_geographies", "summary": (
                     "Two high-confidence sightings 4km apart within 5 minutes. "
                     "Could indicate look-alike or an error in geocoding."
                 ), "attached_message_ids": []}},
                {"tool_name": "categorize_alert", "mode": "suggest",
                 "approval_status": "pending",
                 "args": {"alert_id": flagship.alert_id,
                          "category": "missing_person",
                          "urgency_tier": "critical",
                          "urgency_score": 0.94,
                          "reason": "Sighting density + age of subject warrants critical."}},
            ],
        ))

    # Persist
    for alert_id, bucket_key, summary, calls_spec in decision_recipes:
        decision = AgentDecision(
            ngo_id=ngo.ngo_id,
            bucket_key=bucket_key,
            model="claude-sonnet-4-5",
            prompt_hash=hashlib.sha256(bucket_key.encode()).hexdigest(),
            reasoning_summary=summary,
            tool_calls=[{"name": c["tool_name"], "args": c["args"], "mode": c["mode"]}
                        for c in calls_spec],
            turns=[
                {"role": "system", "content": "matching-engine system prompt (truncated)"},
                {"role": "user", "content": "bucket prompt + initial context (truncated)"},
                {"role": "assistant",
                 "content": summary,
                 "tool_calls": [{"name": c["tool_name"], "args": c["args"]}
                                for c in calls_spec]},
            ],
            total_turns=3,
            latency_ms=4200,
            cost_usd=0.062,
        )
        db.add(decision)
        await db.flush()
        decisions.append(decision)

        for c in calls_spec:
            tc = ToolCall(
                ngo_id=ngo.ngo_id,
                decision_id=decision.decision_id,
                tool_name=c["tool_name"],
                args=c["args"],
                idempotency_key=_idem(bucket_key, c["tool_name"], json.dumps(c["args"], sort_keys=True)),
                mode=c["mode"],
                approval_status=c["approval_status"],
                status="pending" if c["approval_status"] == "pending" else "done",
            )
            db.add(tc)
            await db.flush()
            tool_calls.append(tc)

            # Materialize OutboundMessage for executed sends so the case
            # timeline shows the agent's reply.
            if c["tool_name"] == "send" and c["approval_status"] == "auto_executed":
                bodies = c["args"].get("bodies") or {}
                first_lang = next(iter(bodies)) if bodies else "en"
                db.add(OutboundMessage(
                    ngo_id=ngo.ngo_id,
                    tool_call_id=tc.call_id,
                    recipient_phone=str(c["args"].get("audience", {}).get("phone")
                                        or "audience:unknown"),
                    channel="app",
                    body=bodies.get(first_lang) or "",
                    language=first_lang,
                    status="delivered",
                ))

    await db.flush()
    return decisions, tool_calls


async def _seed_bad_actors(db: AsyncSession, ngo: NGO) -> list[BadActor]:
    actors: list[BadActor] = []
    for phone in _BAD_ACTOR_PHONES:
        b = BadActor(
            phone=phone,
            ngo_id=ngo.ngo_id,
            reason="Repeatedly submitted false sightings during prior alerts.",
            marked_by="agent",
            expires_at=_now() + timedelta(hours=24),
        )
        db.add(b)
        actors.append(b)
    await db.flush()
    return actors


async def _seed_tags(
    db: AsyncSession, ngo: NGO, sightings: list[Sighting]
) -> list[TagAssignment]:
    """A few tags so search(entity='tag_assignment') returns hits."""
    tags = ["high_confidence", "needs_followup", "vehicle_sighting"]
    tag_rows: list[Tag] = []
    for name in tags:
        t = Tag(ngo_id=ngo.ngo_id, namespace="default", name=name, created_by="agent")
        db.add(t)
        tag_rows.append(t)
    await db.flush()

    assigns: list[TagAssignment] = []
    for i, s in enumerate(sightings[:6]):
        t = tag_rows[i % len(tag_rows)]
        ta = TagAssignment(
            ngo_id=ngo.ngo_id,
            tag_id=t.tag_id,
            entity_type="sighting",
            entity_id=s.sighting_id,
            confidence=0.82,
            applied_by="agent",
            alert_id=s.alert_id,
        )
        db.add(ta)
        assigns.append(ta)
    await db.flush()
    return assigns


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def seed_rich(db: AsyncSession, *, reset: bool = False) -> dict[str, Any]:
    """Top-level entry point. Idempotent unless reset=True."""
    if reset:
        await _wipe_warchild(db)
    else:
        existing = await _existing_summary(db)
        if existing is not None:
            return existing

    ngo, accounts_by_region = await _create_ngo_and_accounts(db)
    alerts = await _create_alerts(db, ngo, accounts_by_region)
    buckets_by_alert = await _seed_messages_buckets_and_triage(
        db, ngo, alerts, accounts_by_region
    )
    sightings = await _seed_sightings(db, ngo, alerts)
    clusters, trajectories = await _seed_clusters_and_trajectory(
        db, ngo, alerts, sightings
    )
    decisions, tool_calls = await _seed_decisions_and_toolcalls(
        db, ngo, alerts, buckets_by_alert, sightings
    )
    tag_assigns = await _seed_tags(db, ngo, sightings)
    bad_actors = await _seed_bad_actors(db, ngo)

    await db.commit()

    pending = sum(1 for tc in tool_calls if tc.approval_status == "pending")
    accounts_total = sum(len(v) for v in accounts_by_region.values())
    inbound_total = sum(
        len(_INBOUND_BY_REGION.get(rk, [])) for rk in _INBOUND_BY_REGION
    )

    return {
        "ok": True,
        "ngo_id": ngo.ngo_id,
        "alert_id": alerts[0].alert_id if alerts else "",
        "seeded": {
            "accounts": accounts_total,
            "alerts": len(alerts),
            "alert_deliveries": sum(len(v) for v in accounts_by_region.values()),
            "inbound_messages": inbound_total,
            "sightings": len(sightings),
            "clusters": len(clusters),
            "trajectories": len(trajectories),
            "agent_decisions": len(decisions),
            "tool_calls": len(tool_calls),
            "pending_suggestions": pending,
            "tag_assignments": len(tag_assigns),
            "bad_actors": len(bad_actors),
        },
        "alreadyExisted": False,
    }
