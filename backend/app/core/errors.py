from __future__ import annotations

from typing import Any

from fastapi import Request

from app.core.logging import get_request_id


def error_payload(
    *,
    code: str,
    message: str,
    detail: Any = None,
    request: Request | None = None,
) -> dict[str, Any]:
    request_id = _request_id(request)
    return {
        "detail": detail if detail is not None else message,
        "code": code,
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "detail": detail if detail is not None else message,
            "request_id": request_id,
        },
    }


def _request_id(request: Request | None) -> str | None:
    if request is not None:
        state_request_id = getattr(request.state, "request_id", None)
        if isinstance(state_request_id, str) and state_request_id:
            return state_request_id
    return get_request_id() or None
