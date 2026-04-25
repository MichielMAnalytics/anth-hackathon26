from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    db_ok = (await db.execute(text("SELECT 1"))).scalar() == 1
    return {"status": "ok", "db": "ok" if db_ok else "fail"}
