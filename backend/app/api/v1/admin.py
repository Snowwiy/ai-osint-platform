from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.schemas.governance import (
    AdminOverviewResponse,
    AdminSettingsResponse,
    AdminSettingsUpdate,
    FeatureAvailabilityResponse,
    FeatureFlagUpdate,
    RetentionStatusResponse,
    RetentionUpdate,
)
from app.schemas.qa import AdminQaStatusResponse, DemoSeedResponse
from app.schemas.user import (
    AccountStatus,
    AdminUserListResponse,
    PlatformRole,
    UserAdminActionResponse,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.services.admin import get_health_status, get_platform_stats
from app.services.audit import list_audit_events, record_event, to_audit_response
from app.services.demo import clear_demo_workspace, set_demo_workspace_enabled
from app.services.governance import (
    get_admin_overview,
    get_admin_settings,
    get_feature_availability,
    get_retention_status,
    update_admin_settings,
    update_feature_flags,
    update_retention,
)
from app.services.qa import get_qa_status
from app.services.user import (
    UnsafeUserChangeError,
    UserNotFoundError,
    approve_user,
    disable_user,
    get_user,
    list_users,
    reactivate_user,
    reject_user,
    set_user_role,
    set_user_status,
)

router = APIRouter()


@router.get("/features", response_model=FeatureAvailabilityResponse)
async def feature_availability(
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> FeatureAvailabilityResponse:
    return await get_feature_availability(db)


@router.get("/admin/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await get_health_status(db, request.app.state.redis)


@router.get("/admin/stats")
async def stats(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, int]]:
    return await get_platform_stats(db)


@router.get("/admin/audit", response_model=AuditLogListResponse)
async def audit_events(
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    investigation_id: uuid.UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    try:
        total, events = await list_audit_events(
            db,
            action=action,
            resource_type=resource_type,
            actor_id=actor_id,
            investigation_id=investigation_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    except Exception:
        total, events = 0, []
    return AuditLogListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[to_audit_response(event) for event in events],
    )


@router.get("/admin/settings", response_model=AdminSettingsResponse)
async def admin_settings(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminSettingsResponse:
    return await get_admin_settings(db)


@router.patch("/admin/settings", response_model=AdminSettingsResponse)
async def update_settings(
    body: AdminSettingsUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminSettingsResponse:
    return await update_admin_settings(db, current_user, body)


@router.get("/admin/feature-flags", response_model=FeatureAvailabilityResponse)
async def admin_feature_flags(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> FeatureAvailabilityResponse:
    return await get_feature_availability(db)


@router.patch("/admin/feature-flags", response_model=FeatureAvailabilityResponse)
async def update_admin_feature_flags(
    body: FeatureFlagUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> FeatureAvailabilityResponse:
    return await update_feature_flags(db, current_user, body.feature_flags)


@router.get("/admin/retention", response_model=RetentionStatusResponse)
async def admin_retention(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RetentionStatusResponse:
    return await get_retention_status(db)


@router.patch("/admin/retention", response_model=RetentionStatusResponse)
async def update_admin_retention(
    body: RetentionUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RetentionStatusResponse:
    return await update_retention(db, current_user, body)


@router.get("/admin/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminOverviewResponse:
    return await get_admin_overview(db)


@router.get("/admin/users", response_model=AdminUserListResponse)
async def admin_list_users(
    role: PlatformRole | None = Query(default=None),
    status: AccountStatus | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    total, users = await list_users(
        db,
        role=role,
        status=status,
        search=search,
        limit=limit,
        skip=offset,
    )
    return AdminUserListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[UserResponse.model_validate(user) for user in users],
    )


@router.patch("/admin/users/{user_id}/status", response_model=UserAdminActionResponse)
async def admin_update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserAdminActionResponse:
    try:
        user, old_status, new_status = await set_user_status(
            db,
            target_user_id=user_id,
            actor=current_user,
            status=body.status,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except UnsafeUserChangeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _record_user_admin_event(
        db,
        request,
        actor=current_user,
        target=user,
        action=_status_audit_action(old_status, new_status),
        metadata={"old_status": old_status, "new_status": new_status},
    )
    return UserAdminActionResponse(
        user=UserResponse.model_validate(user),
        message=f"User status changed to {new_status}.",
    )


@router.patch("/admin/users/{user_id}/role", response_model=UserAdminActionResponse)
async def admin_update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserAdminActionResponse:
    try:
        user, old_role, new_role = await set_user_role(
            db,
            target_user_id=user_id,
            actor=current_user,
            role=body.role,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except UnsafeUserChangeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _record_user_admin_event(
        db,
        request,
        actor=current_user,
        target=user,
        action="user.role_changed",
        metadata={"old_role": old_role, "new_role": new_role},
    )
    return UserAdminActionResponse(
        user=UserResponse.model_validate(user),
        message=f"User role changed to {new_role}.",
    )


@router.post("/admin/users/{user_id}/approve", response_model=UserAdminActionResponse)
async def admin_approve_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserAdminActionResponse:
    return await _status_action_response(
        db,
        request,
        actor=current_user,
        target_user_id=user_id,
        action_name="approve",
    )


@router.post("/admin/users/{user_id}/reject", response_model=UserAdminActionResponse)
async def admin_reject_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserAdminActionResponse:
    return await _status_action_response(
        db,
        request,
        actor=current_user,
        target_user_id=user_id,
        action_name="reject",
    )


@router.post("/admin/users/{user_id}/disable", response_model=UserAdminActionResponse)
async def admin_disable_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserAdminActionResponse:
    return await _status_action_response(
        db,
        request,
        actor=current_user,
        target_user_id=user_id,
        action_name="disable",
    )


@router.post("/admin/users/{user_id}/reactivate", response_model=UserAdminActionResponse)
async def admin_reactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserAdminActionResponse:
    return await _status_action_response(
        db,
        request,
        actor=current_user,
        target_user_id=user_id,
        action_name="reactivate",
    )


@router.get("/admin/users/{user_id}", response_model=UserResponse)
async def admin_get_user(
    user_id: uuid.UUID,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        return await get_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@router.get("/admin/qa/status", response_model=AdminQaStatusResponse)
async def admin_qa_status(
    request: Request,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminQaStatusResponse:
    return await get_qa_status(db, request.app.state.redis)


@router.post("/admin/demo/seed", response_model=DemoSeedResponse)
async def seed_demo_workspace(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DemoSeedResponse:
    availability = await get_feature_availability(db)
    if not availability.feature_flags.enable_demo_mode:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "feature_disabled",
                "message": (
                    "Demo mode is disabled. Enable it in Admin Settings first."
                ),
            },
        )
    return await set_demo_workspace_enabled(db, current_user, enabled=True)


@router.delete("/admin/demo/clear", response_model=DemoSeedResponse)
async def clear_demo_workspace_endpoint(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DemoSeedResponse:
    return await clear_demo_workspace(db, current_user)


async def _status_action_response(
    db: AsyncSession,
    request: Request,
    *,
    actor: User,
    target_user_id: uuid.UUID,
    action_name: str,
) -> UserAdminActionResponse:
    try:
        if action_name == "approve":
            user, old_status, new_status = await approve_user(
                db,
                target_user_id=target_user_id,
                actor=actor,
            )
        elif action_name == "reject":
            user, old_status, new_status = await reject_user(
                db,
                target_user_id=target_user_id,
                actor=actor,
            )
        elif action_name == "disable":
            user, old_status, new_status = await disable_user(
                db,
                target_user_id=target_user_id,
                actor=actor,
            )
        elif action_name == "reactivate":
            user, old_status, new_status = await reactivate_user(
                db,
                target_user_id=target_user_id,
                actor=actor,
            )
        else:
            raise HTTPException(status_code=422, detail="Unsupported user action.")
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except UnsafeUserChangeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    action = _status_audit_action(old_status, new_status)
    await _record_user_admin_event(
        db,
        request,
        actor=actor,
        target=user,
        action=action,
        metadata={"old_status": old_status, "new_status": new_status},
    )
    return UserAdminActionResponse(
        user=UserResponse.model_validate(user),
        message=_status_message(action_name, user.account_status),
    )


async def _record_user_admin_event(
    db: AsyncSession,
    request: Request,
    *,
    actor: User,
    target: User,
    action: str,
    metadata: dict[str, str],
) -> None:
    await record_event(
        db,
        action=action,
        actor_id=actor.id,
        resource_type="user",
        resource_id=target.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "target_user_id": str(target.id),
            "actor_user_id": str(actor.id),
            **metadata,
        },
    )


def _status_audit_action(old_status: str, new_status: str) -> str:
    if new_status == "active" and old_status in {"pending", "rejected"}:
        return "user.approved"
    if new_status == "active":
        return "user.reactivated"
    if new_status == "rejected":
        return "user.rejected"
    if new_status == "disabled":
        return "user.disabled"
    return "user.status_changed"


def _status_message(action_name: str, status: str) -> str:
    if action_name == "approve":
        return "User approved and activated."
    if action_name == "reject":
        return "User registration rejected."
    if action_name == "disable":
        return "User disabled."
    if action_name == "reactivate":
        return "User reactivated."
    return f"User status changed to {status}."
