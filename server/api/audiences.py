from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from server.api.auth_dep import current_operator
from server.api.registry import AUDIENCES

router = APIRouter(prefix="/api")


@router.get("/audiences")
async def list_audiences(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
) -> list[dict[str, Any]]:
    return AUDIENCES
