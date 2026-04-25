"""High-level dispatcher: opaque bundle bytes → InboundMessage row.

Called by the hub's transport adapters:
- The `/app/dtn/deliver` HTTP route (a teammate's slice) for bundles
  arriving from internet-bearing carriers.
- The `pybitchat` mesh adapter for bundles arriving directly over BLE.

Pure async function. The caller owns transaction scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from server.db.messages import InboundMessage
from server.dtn.amber import (
    GeneralMessagePayload,
    LocationReportPayload,
    ProfileUpdatePayload,
    SightingPayload,
)
from server.dtn.packets import DTNBundle, InnerType
from server.dtn.seal import open as seal_open
from server.dtn.store import SeenStore


@dataclass
class DispatchResult:
    """Outcome of dispatching a single bundle."""

    bundle_id: Optional[bytes]
    inner_type: Optional[int]
    inserted_msg_id: Optional[str]
    duplicate: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and (self.duplicate or self.inserted_msg_id is not None)


async def dispatch_bundle(
    raw: bytes,
    *,
    db: AsyncSession,
    hub_private_key: bytes,
    source_channel: str,
    ngo_id: str,
    sender_phone: str,
    seen_store: Optional[SeenStore] = None,
) -> DispatchResult:
    """Decode `raw` bundle bytes, decrypt the inner payload, decode the
    amber TLV, and insert a corresponding `InboundMessage` row.

    Args:
        source_channel: written verbatim into `InboundMessage.channel`.
            Pass `'dtn'` for the HTTP path, `'mesh'` for direct mesh ingress.
        ngo_id: the NGO this hub serves (caller resolves from auth context).
        sender_phone: the resolved sender phone, must exist in `account`.
            The caller (HTTP route or mesh transport) is responsible for
            verifying the bundle's Ed25519 signature against the sender's
            `Account.bitchat_pubkey` and passing the resulting phone here.
            If the caller can't resolve, it should reject the bundle
            *before* calling this function rather than calling with a
            placeholder — `sender_phone` is FK-constrained.
    """
    bundle = DTNBundle.decode(raw)
    if bundle is None:
        return DispatchResult(
            bundle_id=None,
            inner_type=None,
            inserted_msg_id=None,
            error="malformed_bundle",
        )

    now = datetime.now(timezone.utc)
    if bundle.expires_at <= int(now.timestamp()):
        return DispatchResult(
            bundle_id=bundle.bundle_id,
            inner_type=bundle.inner_type,
            inserted_msg_id=None,
            error="expired",
        )

    # Idempotency check.
    if seen_store is not None and await seen_store.has_seen(bundle.bundle_id):
        return DispatchResult(
            bundle_id=bundle.bundle_id,
            inner_type=bundle.inner_type,
            inserted_msg_id=None,
            duplicate=True,
        )

    # Decrypt.
    try:
        plaintext = seal_open(
            bundle.ephemeral_pubkey,
            bundle.nonce,
            bundle.ciphertext,
            hub_private_key,
        )
    except Exception as exc:  # noqa: BLE001 — wrap any crypto failure
        return DispatchResult(
            bundle_id=bundle.bundle_id,
            inner_type=bundle.inner_type,
            inserted_msg_id=None,
            error=f"decrypt_failed: {type(exc).__name__}",
        )

    # Decode by inner type.
    body, alert_id_ref, location_geohash, raw_payload = _decode_inner(
        bundle.inner_type, plaintext
    )
    if body is None:
        return DispatchResult(
            bundle_id=bundle.bundle_id,
            inner_type=bundle.inner_type,
            inserted_msg_id=None,
            error="unsupported_or_malformed_inner_payload",
        )

    msg = InboundMessage(
        ngo_id=ngo_id,
        channel=source_channel,
        sender_phone=sender_phone,
        in_reply_to_alert_id=alert_id_ref,
        body=body,
        media_urls=[],
        raw=raw_payload,
    )
    db.add(msg)
    await db.flush()

    if seen_store is not None:
        await seen_store.mark_seen(bundle.bundle_id)

    return DispatchResult(
        bundle_id=bundle.bundle_id,
        inner_type=bundle.inner_type,
        inserted_msg_id=msg.msg_id,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_inner(
    inner_type: int, plaintext: bytes
) -> tuple[Optional[str], Optional[str], Optional[str], dict]:
    """Return (body, alert_id, location_geohash, raw_dict) for the inner.

    `body` is a free-text representation suitable for InboundMessage.body
    (so triage can reason about it without caring which inner type it
    came from). `raw_dict` is a structured snapshot stored on
    `InboundMessage.raw` for audit/replay.
    """
    if inner_type == InnerType.SIGHTING:
        s = SightingPayload.decode(plaintext)
        if s is None:
            return None, None, None, {}
        return (
            s.free_text,
            s.case_id,
            None,
            {
                "kind": "sighting",
                "client_msg_id": s.client_msg_id,
                "case_id": s.case_id,
                "free_text": s.free_text,
                "observed_at": s.observed_at,
                "location_lat": s.location_lat,
                "location_lng": s.location_lng,
            },
        )
    if inner_type == InnerType.LOCATION_REPORT:
        l = LocationReportPayload.decode(plaintext)
        if l is None:
            return None, None, None, {}
        safety = "safe" if l.safety == 0x01 else "unsafe" if l.safety == 0x02 else "unknown"
        body = f"[location_report:{safety}] {l.note}".strip()
        return (
            body,
            None,
            None,
            {
                "kind": "location_report",
                "client_msg_id": l.client_msg_id,
                "lat": l.lat,
                "lng": l.lng,
                "safety": safety,
                "note": l.note,
                "observed_at": l.observed_at,
            },
        )
    if inner_type == InnerType.GENERAL_MESSAGE:
        g = GeneralMessagePayload.decode(plaintext)
        if g is None:
            return None, None, None, {}
        return (
            g.body,
            None,
            None,
            {
                "kind": "general_message",
                "client_msg_id": g.client_msg_id,
                "body": g.body,
                "sent_at": g.sent_at,
            },
        )
    if inner_type == InnerType.PROFILE_UPDATE:
        p = ProfileUpdatePayload.decode(plaintext)
        if p is None:
            return None, None, None, {}
        body = f"[profile_update] {p.name} ({p.phone_number}, {p.language})"
        return (
            body,
            None,
            None,
            {
                "kind": "profile_update",
                "name": p.name,
                "phone_number": p.phone_number,
                "language": p.language,
                "profession": p.profession,
            },
        )
    return None, None, None, {}


