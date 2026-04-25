"""Lightweight operator auth dependency.

Reads the X-Operator-Id request header and resolves it against the
static registry. JWT bridging is deferred to a later plan.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header, HTTPException

from server.api.registry import get_operator_by_id


async def current_operator(
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> dict[str, Any]:
    if not x_operator_id:
        raise HTTPException(status_code=401, detail="Missing X-Operator-Id header")
    op = get_operator_by_id(x_operator_id)
    if op is None:
        raise HTTPException(status_code=401, detail="Unknown operator")
    return op
