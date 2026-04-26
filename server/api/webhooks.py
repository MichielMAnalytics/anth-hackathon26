"""External webhook handlers (currently: Twilio inbound SMS).

Twilio POSTs application/x-www-form-urlencoded with at minimum:
  From, To, Body, MessageSid, AccountSid

We validate the X-Twilio-Signature header, normalise the payload into an
InboundMessage row, and publish `new_inbound` so the agent picks it up.
The endpoint always returns valid TwiML so Twilio doesn't retry on a
non-200, even when we silently swallow validation failures.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.alerts import REPLY_CODE_ALPHABET, REPLY_CODE_LEN, Alert
from server.db.base import generate_ulid
from server.db.engine import get_engine
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage
from server.db.session import get_db
from server.eventbus.postgres import PostgresEventBus
from server.integrations import twilio_sms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks")

# Match a reply-code prefix at the start of an inbound SMS body. We accept
# any of "-", "—", "–", ":" or just whitespace as the separator, and the
# code itself is case-insensitive.
_CODE_RE = re.compile(
    rf"^\s*([{REPLY_CODE_ALPHABET}{REPLY_CODE_ALPHABET.lower()}]{{{REPLY_CODE_LEN}}})\s*[-–—:]?\s*(.*)$",
    re.DOTALL,
)


async def _resolve_reply_code(
    db: AsyncSession, ngo_id: str, body: str
) -> tuple[Optional[str], str]:
    """If body starts with a known reply code, return (alert_id, stripped_body).

    Returns (None, original_body) when no code matches an active alert.
    """
    m = _CODE_RE.match(body)
    if not m:
        return None, body
    code = m.group(1).upper()
    rest = m.group(2).strip()
    alert_id = (
        await db.execute(
            select(Alert.alert_id).where(
                Alert.ngo_id == ngo_id,
                Alert.reply_code == code,
                Alert.status == "active",
            )
        )
    ).scalar_one_or_none()
    if alert_id is None:
        return None, body
    # Strip the prefix only when it actually matched a case — otherwise the
    # original body might just happen to start with 4 letters.
    return alert_id, rest or body

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _twiml() -> Response:
    return Response(content=_EMPTY_TWIML, media_type="application/xml")


async def _ensure_account(db: AsyncSession, phone: str) -> Optional[str]:
    """Upsert a minimal Account so the InboundMessage FK is satisfied.

    Returns the ngo_id we assigned, or None if no NGO exists yet.
    """
    existing = (
        await db.execute(select(Account).where(Account.phone == phone))
    ).scalar_one_or_none()
    if existing:
        return existing.ngo_id

    first_ngo = (await db.execute(select(NGO))).scalars().first()
    if first_ngo is None:
        return None

    stmt = (
        pg_insert(Account.__table__)
        .values(phone=phone, ngo_id=first_ngo.ngo_id, source="sms")
        .on_conflict_do_nothing(index_elements=["phone"])
    )
    await db.execute(stmt)
    return first_ngo.ngo_id


def _validate_signature(request: Request, form: dict[str, str]) -> bool:
    """Verify Twilio's X-Twilio-Signature header. Skip when no token configured."""
    token = twilio_sms.auth_token()
    if not token:
        # Stub mode — skip validation so the route is still usable for tests.
        return True
    sig = request.headers.get("X-Twilio-Signature")
    if not sig:
        return False
    try:
        from twilio.request_validator import RequestValidator
    except Exception:  # noqa: BLE001
        logger.warning("twilio: SDK not installed — accepting webhook unverified")
        return True
    # Twilio signs the full public URL (scheme + host + path) it called.
    # When behind a tunnel/proxy, X-Forwarded-Proto/Host may differ from
    # request.url. Honour them if present.
    fwd_proto = request.headers.get("x-forwarded-proto")
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if fwd_proto and fwd_host:
        url = f"{fwd_proto}://{fwd_host}{request.url.path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
    else:
        url = str(request.url)
    return RequestValidator(token).validate(url, form, sig)


@router.post("/twilio/sms")
async def twilio_inbound(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raw = await request.form()
    form = {k: str(v) for k, v in raw.items()}

    if not _validate_signature(request, form):
        logger.warning("twilio inbound: signature mismatch from %s", request.client)
        # Return 200 OK + empty TwiML so Twilio doesn't pile on retries,
        # but log it loudly. Don't persist the message.
        return _twiml()

    sender = (form.get("From") or "").strip()
    body = (form.get("Body") or "").strip()
    sid = form.get("MessageSid")
    if not sender or not body:
        logger.info("twilio inbound: empty From/Body — ignoring sid=%s", sid)
        return _twiml()

    ngo_id = await _ensure_account(db, sender)
    if not ngo_id:
        logger.warning("twilio inbound: no NGO seeded — dropping inbound from %s", sender)
        return _twiml()

    alert_id, body = await _resolve_reply_code(db, ngo_id, body)

    msg_id = generate_ulid()
    db.add(
        InboundMessage(
            msg_id=msg_id,
            ngo_id=ngo_id,
            channel="sms",
            sender_phone=sender,
            in_reply_to_alert_id=alert_id,
            body=body,
            media_urls=[],
            raw={"twilio": form},
            status="new",
        )
    )
    await db.commit()

    try:
        bus = PostgresEventBus(get_engine())
        await bus.publish("new_inbound", msg_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("twilio inbound: publish failed: %s", exc)

    logger.info(
        "twilio inbound: persisted msg=%s sid=%s from=%s case=%s",
        msg_id,
        sid,
        sender,
        alert_id or "-",
    )
    return _twiml()
