from fastapi import APIRouter, Depends, FastAPI, Query
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.permissions import require_admin
from components.notification.operations_metrics import external_delivery_metrics
from components.realtime import realtime_service
from components.realtime.pool_metrics import realtime_pool_health
from database import Database
from utils.database_metrics import database_pool_health
from utils.http_metrics import http_runtime_metrics


def install(app: FastAPI) -> None:
    router = APIRouter(
        prefix="/admin/operations",
        tags=["admin-operations"],
        dependencies=[Depends(require_admin)],
    )

    @router.get("/external-delivery")
    async def delivery_metrics(
        window_hours: int = Query(default=24, ge=1, le=720),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        metrics = await external_delivery_metrics(db, window_hours=window_hours)
        return {"status": "ok", "metrics": metrics}

    @router.get("/realtime-redis")
    async def realtime_redis_metrics():
        return {"status": "ok", "metrics": realtime_pool_health(realtime_service)}

    @router.get("/postgres-pool")
    async def postgres_pool_metrics():
        return {"status": "ok", "metrics": database_pool_health()}

    @router.get("/http")
    async def http_metrics():
        return {"status": "ok", "metrics": http_runtime_metrics.snapshot()}

    app.include_router(router)
