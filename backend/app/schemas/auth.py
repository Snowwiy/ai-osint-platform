from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.user import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    password: str

    @model_validator(mode="after")
    def require_identifier(self) -> LoginRequest:
        if not self.email and not self.username:
            raise ValueError("email or username is required")
        return self


class RegistrationPolicyResponse(BaseModel):
    public_registration_enabled: bool
    requires_approval: bool
    invite_code_required: bool
    default_role: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str
    full_name: str | None = Field(default=None, max_length=120)
    invite_code: str | None = Field(default=None, max_length=120)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        clean = value.strip().lower()
        if not clean:
            raise ValueError("username is required")
        if not 2 <= len(clean) <= 50:
            raise ValueError("username must be 2-50 characters")
        return clean

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("full_name", "invite_code")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class RegisterResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    account_status: Literal["active", "pending"]
    message: str


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
