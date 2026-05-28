from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    password: str

    @model_validator(mode="after")
    def require_identifier(self) -> LoginRequest:
        if not self.email and not self.username:
            raise ValueError("email or username is required")
        return self


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = 1800
    user: UserBrief | None = None


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = 1800


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
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


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
