from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.errors import error_payload
from app.core.logging import configure_logging
from app.core.middleware import (
    AuditLogMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.rate_limit import limiter
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings.validate_for_startup()
    for warning in settings.startup_warnings():
        logger.warning("configuration warning: %s", warning)
    await _connect_database()
    app.state.redis = await _connect_redis()
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    configure_logging()
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

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(
        request: Request,
        _exc: RateLimitExceeded,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=error_payload(
                code="RATE_LIMITED",
                message="Too many requests.",
                request=request,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=error_payload(
                code=_error_code(exc.status_code),
                message=_error_message(exc.status_code),
                detail=exc.detail,
                request=request,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                detail=jsonable_encoder(exc.errors()),
                request=request,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                code="INTERNAL_SERVER_ERROR",
                message="An internal error occurred.",
                request=request,
            ),
        )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_body_size=settings.MAX_REQUEST_BODY_BYTES,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    from app.api.v1.router import api_router
    from app.api.health import router as health_router

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app


async def _connect_redis() -> Any:
    last_error: Exception | None = None
    for attempt in range(1, settings.REDIS_CONNECT_RETRIES + 1):
        try:
            redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                encoding="utf-8",
            )
            await redis.ping()
            return redis
        except Exception as exc:
            last_error = exc
            if attempt >= settings.REDIS_CONNECT_RETRIES:
                break
            await _sleep(settings.REDIS_CONNECT_RETRY_SECONDS)
    raise RuntimeError("Unable to connect to Redis during startup") from last_error


async def _connect_database() -> None:
    last_error: Exception | None = None
    for attempt in range(1, settings.DATABASE_CONNECT_RETRIES + 1):
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last_error = exc
            if attempt >= settings.DATABASE_CONNECT_RETRIES:
                break
            await _sleep(settings.DATABASE_CONNECT_RETRY_SECONDS)
    raise RuntimeError("Unable to connect to PostgreSQL during startup") from last_error


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def _error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "REQUEST_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }.get(status_code, "HTTP_ERROR")


def _error_message(status_code: int) -> str:
    return {
        400: "Bad request.",
        401: "Authentication is required.",
        403: "Permission denied.",
        404: "Resource not found.",
        409: "Resource conflict.",
        413: "Request body is too large.",
        422: "Request validation failed.",
        429: "Too many requests.",
    }.get(status_code, "Request failed.")


app = create_app()
