from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from server.api.auth_dep import current_operator
from server.api.registry import OPERATORS

router = APIRouter(prefix="/api")


@router.get("/me")
async def get_me(
    op: Annotated[dict[str, Any], Depends(current_operator)],
) -> dict[str, Any]:
    return op


@router.get("/operators")
async def list_operators() -> list[dict[str, Any]]:
    return OPERATORS
