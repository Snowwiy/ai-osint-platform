from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PlatformRole = Literal["admin", "analyst"]
AccountStatus = Literal["active", "pending", "disabled", "rejected"]


def validate_password_strength(value: str) -> str:
    errors = []
    if len(value) < 12:
        errors.append("at least 12 characters")
    if not any(char.isupper() for char in value):
        errors.append("one uppercase letter")
    if not any(char.islower() for char in value):
        errors.append("one lowercase letter")
    if not any(char.isdigit() for char in value):
        errors.append("one digit")
    if not any(char in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for char in value):
        errors.append("one special character")
    if errors:
        raise ValueError("Password requires: " + ", ".join(errors))
    return value


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = Field(default=None, max_length=120)
    role: PlatformRole = "analyst"

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        clean = value.strip().lower()
        if not 2 <= len(clean) <= 50:
            raise ValueError("username must be 2-50 characters")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ("admin", "analyst"):
            raise ValueError("role must be 'admin' or 'analyst'")
        return value

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=120)
    role: PlatformRole | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in ("admin", "analyst"):
            raise ValueError("role must be 'admin' or 'analyst'")
        return value

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    full_name: str | None = None
    role: str
    status: str
    account_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None
    registration_source: str | None = None
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None


class UserCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: str


class AdminUserListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[UserResponse]


class UserStatusUpdate(BaseModel):
    status: AccountStatus


class UserRoleUpdate(BaseModel):
    role: PlatformRole


class UserAdminActionResponse(BaseModel):
    user: UserResponse
    message: str
