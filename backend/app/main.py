from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.middleware import AuditLogMiddleware
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        encoding="utf-8",
    )
    await app.state.redis.ping()
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RavenTech OSINT Platform",
        description="Authorized, defensive digital footprint analysis.",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        cast(Any, _rate_limit_exceeded_handler),
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal error occurred.",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )

    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
