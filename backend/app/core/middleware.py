from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.errors import error_payload
from app.core.logging import reset_request_id, set_request_id
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.services.audit import record_event

logger = logging.getLogger(__name__)

_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_EXCLUDED_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/api/v1/admin/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}
_DENIED_STATUS_CODES = {401, 403, 404}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(settings.REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        token = set_request_id(request_id)
        started_at = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            if response is not None:
                response.headers[settings.REQUEST_ID_HEADER] = request_id
                logger.info(
                    "request completed",
                    extra={
                        "endpoint": request.url.path,
                        "method": request.method,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )
            reset_request_id(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path not in {"/docs", "/redoc", "/openapi.json"}:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; frame-ancestors 'none'; "
                "img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'",
            )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, max_body_size: int) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        try:
            request_size = int(content_length) if content_length else 0
        except ValueError:
            request_size = 0
        if request_size > self.max_body_size:
            return JSONResponse(
                status_code=413,
                content=error_payload(
                    code="REQUEST_TOO_LARGE",
                    message="Request body is too large.",
                    request=request,
                ),
            )
        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if _should_audit(request, response.status_code):
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

        action = _audit_action(request, status_code)
        investigation_id = _infer_investigation_id(request.url.path)

        try:
            async with AsyncSessionLocal() as db:
                await record_event(
                    db,
                    action=action,
                    actor_id=user_id,
                    resource_type=_infer_resource_type(request.url.path),
                    resource_id=_infer_resource_id(request.url.path),
                    investigation_id=investigation_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    metadata={
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


def _should_audit(request: Request, status_code: int) -> bool:
    if request.url.path in _EXCLUDED_PATHS:
        return False
    suffix = _path_suffix(request.url.path)
    if suffix[:2] == ("auth", "login") and status_code < 400:
        return False
    if suffix[:1] == ("targets",) and status_code < 400:
        return False
    if suffix[:1] == ("analysis",) and status_code < 400:
        return False
    if suffix[:1] == ("recon",) and status_code < 400:
        return False
    if (
        suffix[:1] == ("reports",)
        and suffix[-1:] == ("download",)
        and status_code < 400
    ):
        return False
    if status_code in _DENIED_STATUS_CODES and request.url.path.startswith("/api/v1/"):
        return True
    if request.method in _AUDITED_METHODS:
        return True
    return (
        request.method == "GET"
        and suffix[:1] == ("reports",)
        and suffix[-1:] == ("download",)
    )


def _audit_action(request: Request, status_code: int) -> str:
    path = request.url.path
    suffix = _path_suffix(path)
    if suffix[:2] == ("auth", "login"):
        return "auth.login_success" if status_code < 400 else "auth.login_failure"
    if suffix[:2] == ("auth", "logout"):
        return "auth.logout"
    if status_code in _DENIED_STATUS_CODES:
        return "permission.denied"
    if suffix[:1] == ("investigations",):
        return _investigation_action(request.method, suffix)
    if suffix[:1] == ("targets",):
        return "target.added" if request.method == "POST" else "target.deleted"
    if suffix[:1] == ("recon",):
        return "recon.executed"
    if suffix[:1] == ("analysis",):
        return "ai_analysis.executed"
    if suffix[:1] == ("reports",) and suffix[-1:] == ("download",):
        return "report.downloaded"
    if suffix[:1] == ("findings",):
        return "finding.updated"
    if suffix[:1] == ("tasks",):
        if suffix[-1:] == ("status",):
            return "task.completed" if request.method == "PATCH" else "task.updated"
        return _crud_action(request.method, "task")
    if suffix[:1] == ("evidence",):
        return "evidence.reviewed" if suffix[-1:] == ("review",) else "evidence.updated"
    if suffix[-1:] == ("findings",):
        return "findings.generated"
    return f"{request.method.lower()}{path.replace('/', '.')}"


def _investigation_action(method: str, suffix: tuple[str, ...]) -> str:
    if len(suffix) == 1 and method == "POST":
        return "investigation.created"
    if "reports" in suffix and method == "POST":
        return "report.generated"
    if "notes" in suffix:
        return _crud_action(method, "note")
    if "tasks" in suffix:
        return _crud_action(method, "task")
    if "evidence" in suffix:
        if method == "POST":
            return "evidence.linked"
        return _crud_action(method, "evidence")
    if "findings" in suffix:
        return "findings.generated"
    if len(suffix) >= 2 and method in {"PUT", "PATCH"}:
        return "investigation.updated"
    if len(suffix) >= 2 and method == "DELETE":
        return "investigation.deleted"
    return f"investigation.{method.lower()}"


def _crud_action(method: str, resource: str) -> str:
    if method == "POST":
        return f"{resource}.created"
    if method in {"PUT", "PATCH"}:
        return f"{resource}.updated"
    if method == "DELETE":
        return f"{resource}.deleted"
    return f"{resource}.{method.lower()}"


def _infer_resource_type(path: str) -> str | None:
    resource_map = {
        "admin": "admin",
        "auth": "auth",
        "users": "user",
        "investigations": "investigation",
        "targets": "target",
        "findings": "finding",
        "analysis": "ai_analysis",
        "recon": "recon",
        "reports": "report",
        "notes": "note",
        "tasks": "task",
        "evidence": "evidence",
    }
    segments = [segment for segment in path.split("/") if segment]
    for nested_resource in ("notes", "tasks", "evidence", "reports", "findings"):
        if nested_resource in segments:
            return resource_map[nested_resource]
    for segment in segments:
        if _is_uuid_segment(segment):
            continue
        if segment in resource_map:
            return resource_map[segment]
    return None


def _infer_investigation_id(path: str) -> uuid.UUID | None:
    suffix = _path_suffix(path)
    for index, segment in enumerate(suffix):
        if segment == "investigations" and len(suffix) > index + 1:
            return _parse_uuid(suffix[index + 1])
    return None


def _infer_resource_id(path: str) -> uuid.UUID | None:
    for segment in reversed(_path_suffix(path)):
        parsed = _parse_uuid(segment)
        if parsed is not None:
            return parsed
    return None


def _path_suffix(path: str) -> tuple[str, ...]:
    segments = tuple(segment for segment in path.split("/") if segment)
    if len(segments) >= 2 and segments[:2] == ("api", "v1"):
        return segments[2:]
    return segments


def _is_uuid_segment(segment: str) -> bool:
    return _parse_uuid(segment) is not None


def _parse_uuid(segment: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(segment)
    except ValueError:
        return None
