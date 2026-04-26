"""Thin Twilio SMS adapter.

Reads creds from env. If unset, every call is a no-op stub so docker
compose without creds keeps working.

  TWILIO_ACCOUNT_SID         — required for live mode
  TWILIO_AUTH_TOKEN          — required for live mode
  TWILIO_FROM_NUMBER         — the Twilio number we send from (E.164)
  TWILIO_DEMO_RECIPIENT      — if set, every send is rerouted to this
                               single number (use a verified phone on a
                               Twilio trial account so nothing fans out
                               to real audiences during a demo)
  TWILIO_MAX_RECIPIENTS      — hard cap when fanning out to an audience.
                               Default 25.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SmsResult:
    sid: Optional[str]
    status: str  # "sent" | "queued" | "failed" | "stub"
    error: Optional[str] = None


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v is None:
        return None
    v = v.strip()
    return v or None


def is_configured() -> bool:
    return bool(
        _env("TWILIO_ACCOUNT_SID")
        and _env("TWILIO_AUTH_TOKEN")
        and _env("TWILIO_FROM_NUMBER")
    )


def from_number() -> Optional[str]:
    return _env("TWILIO_FROM_NUMBER")


def auth_token() -> Optional[str]:
    return _env("TWILIO_AUTH_TOKEN")


def demo_recipient() -> Optional[str]:
    return _env("TWILIO_DEMO_RECIPIENT")


def max_recipients() -> int:
    raw = _env("TWILIO_MAX_RECIPIENTS")
    if not raw:
        return 25
    try:
        return max(1, int(raw))
    except ValueError:
        return 25


def rescue_team() -> list[tuple[str, Optional[str]]]:
    """Parse RESCUE_TEAM_RECIPIENTS into [(phone_e164, name_or_None), ...].

    Format: '+316...:Alice,+447...:Bob'. Whitespace within phones is
    stripped so user-friendly inputs like '+44 7786 256893' work.
    Names are optional ('+316...' alone is fine).
    """
    raw = _env("RESCUE_TEAM_RECIPIENTS")
    if not raw:
        return []
    out: list[tuple[str, Optional[str]]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            phone, name = part.split(":", 1)
            phone = phone.strip().replace(" ", "")
            name = name.strip() or None
        else:
            phone = part.replace(" ", "")
            name = None
        if phone:
            out.append((phone, name))
    return out


def _client():
    from twilio.rest import Client

    sid = _env("TWILIO_ACCOUNT_SID")
    tok = _env("TWILIO_AUTH_TOKEN")
    return Client(sid, tok)


def _send_sync(to: str, body: str) -> SmsResult:
    if not is_configured():
        logger.info("twilio: stub send to=%s len=%s (no creds)", to, len(body))
        return SmsResult(sid=None, status="stub")
    try:
        msg = _client().messages.create(
            to=to,
            from_=from_number(),
            body=body,
        )
        return SmsResult(sid=msg.sid, status=msg.status or "queued")
    except Exception as exc:  # noqa: BLE001
        logger.warning("twilio: send failed to=%s: %s", to, exc)
        return SmsResult(sid=None, status="failed", error=str(exc))


async def send_sms(to: str, body: str) -> SmsResult:
    """Send one SMS. Async-friendly wrapper around the sync SDK."""
    return await asyncio.to_thread(_send_sync, to, body)
