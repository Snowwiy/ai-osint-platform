from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.services.health import health_snapshot, liveness_snapshot

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    return await health_snapshot(request.app.state.redis, include_ready=True)


@router.get("/health/live")
async def live() -> dict[str, Any]:
    return await liveness_snapshot()


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    body = await health_snapshot(request.app.state.redis, include_ready=True)
    status_code = (
        status.HTTP_200_OK
        if body["status"] == "ok"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=body)
