from __future__ import annotations

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    total: int
    items: list[T]


class ErrorResponse(BaseModel):
    detail: str
    code: str
    timestamp: str
