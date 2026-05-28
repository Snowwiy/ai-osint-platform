from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.services.audit import record_event

logger = logging.getLogger(__name__)

_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_EXCLUDED_PATHS = {"/api/v1/admin/health", "/docs", "/redoc", "/openapi.json"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if (
            request.method in _AUDITED_METHODS
            and request.url.path not in _EXCLUDED_PATHS
        ):
            await self._write_audit_log(request, response.status_code)
        return response

    async def _write_audit_log(self, request: Request, status_code: int) -> None:
        user_id: uuid.UUID | None = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = decode_token(auth_header[7:])
                user_id = uuid.UUID(payload["sub"])
            except Exception:
                user_id = None

        action = f"{request.method.lower()}{request.url.path.replace('/', '.')}"

        try:
            async with AsyncSessionLocal() as db:
                await record_event(
                    db,
                    action=action,
                    user_id=user_id,
                    resource_type=_infer_resource_type(request.url.path),
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                    },
                )
                await db.commit()
        except Exception:
            logger.exception(
                "AuditLogMiddleware failed for %s %s",
                request.method,
                request.url.path,
            )


def _infer_resource_type(path: str) -> str | None:
    resource_map = {
        "admin": "admin",
        "auth": "auth",
        "users": "user",
        "investigations": "investigation",
        "targets": "target",
        "findings": "finding",
        "analyses": "ai_analysis",
        "reports": "report",
    }
    segments = [segment for segment in path.split("/") if segment]
    for segment in segments:
        if _is_uuid_segment(segment):
            continue
        if segment in resource_map:
            return resource_map[segment]
    return None


def _is_uuid_segment(segment: str) -> bool:
    try:
        uuid.UUID(segment)
        return True
    except ValueError:
        return False
