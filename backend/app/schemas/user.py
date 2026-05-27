from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


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
    role: str = "analyst"

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


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in ("admin", "analyst"):
            raise ValueError("role must be 'admin' or 'analyst'")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class UserCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: str
