"""Hackathon-grade login gate.

Single shared password set via APP_PASSWORD. Frontend POSTs the
password here; on match we return 200, the SPA stores an unlock flag
in localStorage and shows the dashboard.

This is intentionally NOT a per-request auth check — it's a gate to
keep random visitors who stumble onto the public URL from seeing the
operator console. Operator identity still uses X-Operator-Id headers.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth")


class LoginBody(BaseModel):
    password: str


def _expected_password() -> str:
    return (os.environ.get("APP_PASSWORD") or "").strip()


@router.get("/required")
async def auth_required() -> dict:
    """Tell the SPA whether a password is configured at all."""
    return {"required": bool(_expected_password())}


@router.post("/login")
async def auth_login(body: LoginBody) -> dict:
    expected = _expected_password()
    if not expected:
        # No gate configured — anything is fine.
        return {"ok": True}
    # Constant-time compare so timing can't enumerate length / chars.
    if not hmac.compare_digest(body.password.strip(), expected):
        raise HTTPException(status_code=401, detail="invalid password")
    return {"ok": True}
