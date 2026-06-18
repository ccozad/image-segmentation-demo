from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..db import get_session
from ..storage import Storage, get_storage

router = APIRouter()


@router.get("/healthz")
async def healthz(
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> dict[str, str]:
    """Liveness + dependency check: Postgres and object storage reachable."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any DB failure as unhealthy
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}")
    try:
        await run_in_threadpool(storage.check)
    except Exception as exc:  # noqa: BLE001 - report any S3 failure as unhealthy
        raise HTTPException(status_code=503, detail=f"storage unavailable: {exc}")
    return {"status": "ok"}
