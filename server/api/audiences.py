from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from server.api.auth_dep import current_operator
from server.api.registry import AUDIENCES
from server.integrations import twilio_sms

router = APIRouter(prefix="/api")


@router.get("/audiences")
async def list_audiences(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
) -> list[dict[str, Any]]:
    rescue_count = len(twilio_sms.rescue_team())
    out: list[dict[str, Any]] = []
    for a in AUDIENCES:
        if a["id"] == "rescue_team":
            a = {**a, "count": rescue_count}
        out.append(a)
    return out
