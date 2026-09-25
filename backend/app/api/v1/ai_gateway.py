from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, require_feature
from app.models.ai_session import AiMessage, AiSession
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.ai_gateway import (
    AiCatalogResponse,
    AiContextPreviewRequest,
    AiContextPreviewResponse,
    AiMessageRequest,
    AiMessageResult,
    AiModelTestRequest,
    AiModelTestResponse,
    AiOperationsStatus,
    AiPreferences,
    AiPreferencesUpdate,
    AiPromptCopyAuditRequest,
    AiPromptHandoffRequest,
    AiPromptHandoffResponse,
    AiProvider,
    AiRuntimeStatus,
    AiSessionCreate,
    AiSessionRename,
    AiSessionView,
    AiToolExecuteRequest,
)
from app.services.ai.gateway_service import (
    AiStreamSanitizer,
    build_context_prompt,
    build_prompt_handoff,
    execution_for_model,
    get_adapter,
    get_preferences,
    get_user_session,
    is_free_or_local,
    list_user_sessions,
    load_selected_context,
    model_view,
    next_message_sequence,
    preview_knowledge_context,
    require_allowed_model,
    sanitize_ai_text,
    save_preferences,
    session_view,
)
from app.services.ai.opencode_adapter import ModelRecord, OpenCodeAdapter
from app.services.ai.tool_gateway import (
    NativeInventory,
    build_evidence_followup,
    build_tool_aware_prompt,
    execute_model_tool_calls,
    execute_tool,
    parse_model_tool_request,
    registered_tools,
    workflow_calls,
)
from app.services.ai.tool_gateway import (
    sanitize_text as sanitize_tool_text,
)
from app.services.audit import record_event

router = APIRouter(
    prefix="/ai",
    tags=["ai-model-gateway"],
    dependencies=[Depends(require_feature("enable_ai_analysis"))],
)
_CHAT_ROLES = {"admin", "analyst"}
_ACTIVE_STREAMS: dict[uuid.UUID, asyncio.Event] = {}
_SAFE_TOOL_ERROR_CODES = {
    "unknown_tool",
    "authorization_denied",
    "invalid_arguments",
    "rate_limited",
    "cancelled",
    "timeout",
    "scope_denied",
    "not_found",
    "tool_unavailable",
    "tool_budget_exceeded",
    "turn_row_budget_exceeded",
}


@router.get("/tools")
async def list_ai_tools_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    _require_chat_role(current_user)
    items = registered_tools(current_user)
    return {
        "items": items,
        "total": len(items),
        "read_only_count": sum(bool(item["read_only"]) for item in items),
        "write_count": 0,
        "shell_available": False,
        "sql_available": False,
        "filesystem_available": False,
        "protocol": (
            "RavenTech bounded JSON tool request; OpenCode built-in tools remain denied"
        ),
    }


@router.post("/tools/execute")
async def execute_ai_tool_endpoint(
    body: AiToolExecuteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    _require_chat_role(current_user)
    inventory: NativeInventory | None = None
    if body.desktop_inventory is not None:
        try:
            inventory = NativeInventory.model_validate(body.desktop_inventory)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Desktop inventory did not match the bounded read-only schema.",
            ) from None
    result = await execute_tool(
        db,
        current_user,
        body.tool_id,
        body.arguments,
        native_inventory=inventory,
        request=request,
        redis=getattr(request.app.state, "redis", None),
    )
    await db.commit()
    return result


@router.get("/runtime")
async def ai_runtime_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    _require_chat_role(current_user)
    adapter = get_adapter()
    runtime = await adapter.get_runtime()
    providers, models = await adapter.discover()
    runtime["provider_count"] = len(providers)
    runtime["available_model_count"] = sum(1 for item in models if item.available)
    runtime["dependency"] = "optional"
    return runtime


@router.get("/operations-status", response_model=AiOperationsStatus)
async def ai_operations_status_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiOperationsStatus:
    _require_admin(current_user)
    adapter = get_adapter()
    runtime = await adapter.get_runtime()
    providers, models = await adapter.discover()
    last_refresh = (
        await db.execute(
            select(AuditLog.timestamp)
            .where(AuditLog.action == "ai.models_refreshed")
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_inference = (
        await db.execute(
            select(AuditLog.timestamp)
            .where(AuditLog.action == "ai.message_completed")
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_tool_activity = (
        await db.execute(
            select(AuditLog.timestamp)
            .where(AuditLog.action.like("ai.tool_%"))
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_successful_tool = (
        await db.execute(
            select(AuditLog.timestamp)
            .where(AuditLog.action == "ai.tool_completed")
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_tool_failure = (
        await db.execute(
            select(AuditLog.event_metadata)
            .where(AuditLog.action.in_(("ai.tool_denied", "ai.tool_failed")))
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_tool_error = (
        last_tool_failure.get("safe_error_code")
        if isinstance(last_tool_failure, dict)
        else None
    )
    if last_tool_error not in _SAFE_TOOL_ERROR_CODES:
        last_tool_error = None
    tool_gateway_degraded = last_tool_error in {"timeout", "tool_unavailable"}
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    tool_requests_last_hour = int(
        (
            await db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action.in_(
                        ("ai.tool_completed", "ai.tool_denied", "ai.tool_failed")
                    ),
                    AuditLog.timestamp >= hour_ago,
                )
            )
        ).scalar_one()
    )
    denied_tool_attempts = int(
        (
            await db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action == "ai.tool_denied",
                    AuditLog.timestamp >= hour_ago,
                )
            )
        ).scalar_one()
    )
    preferences = await get_preferences(db, current_user.id)
    available = sum(item.available for item in models)
    connected_local = sum(
        bool(item.get("local")) and bool(item.get("connected"))
        for item in providers
        if isinstance(item, dict)
    )
    connected_remote = sum(
        bool(item.get("remote")) and bool(item.get("connected"))
        for item in providers
        if isinstance(item, dict)
    )
    return AiOperationsStatus(
        runtime_status=str(runtime.get("status", "unsupported")),
        runtime_available=bool(runtime.get("available")),
        available_models=available,
        local_providers=connected_local,
        remote_providers=connected_remote,
        selected_model_id=preferences.selected_model_id,
        last_model_refresh=last_refresh,
        last_successful_inference=last_inference,
        degraded=not bool(runtime.get("available")) and connected_local == 0,
        message=str(runtime.get("message", "AI integration is optional.")),
        tool_gateway_status="degraded" if tool_gateway_degraded else "healthy",
        registered_tools=len(registered_tools(current_user)),
        read_only_tool_count=len(registered_tools(current_user)),
        write_tool_count=0,
        last_tool_activity=last_tool_activity,
        last_successful_tool=last_successful_tool,
        last_tool_error=last_tool_error,
        tool_requests_last_hour=tool_requests_last_hour,
        denied_tool_attempts=denied_tool_attempts,
    )


@router.get("/providers")
async def ai_providers_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    _require_chat_role(current_user)
    providers, _models = await get_adapter().discover()
    return {"items": providers}


@router.get("/models", response_model=AiCatalogResponse)
async def ai_models_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiCatalogResponse:
    _require_chat_role(current_user)
    return await _catalog(
        get_adapter(),
        refresh=False,
        preferences=await get_preferences(db, current_user.id),
    )


@router.post("/models/refresh", response_model=AiCatalogResponse)
async def refresh_ai_models_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiCatalogResponse:
    _require_chat_role(current_user)
    response = await _catalog(
        get_adapter(),
        refresh=True,
        preferences=await get_preferences(db, current_user.id),
    )
    await _audit(
        db,
        request,
        current_user,
        "ai.models_refreshed",
        metadata={"models": len(response.models)},
    )
    return response


@router.get("/preferences", response_model=AiPreferences)
async def get_ai_preferences_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiPreferences:
    _require_chat_role(current_user)
    return await get_preferences(db, current_user.id)


@router.put("/preferences", response_model=AiPreferences)
async def update_ai_preferences_endpoint(
    body: AiPreferencesUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiPreferences:
    _require_chat_role(current_user)
    if body.selected_model_id:
        try:
            await require_allowed_model(
                get_adapter(), body.selected_model_id, body.execution_mode
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    record = await save_preferences(db, current_user.id, body)
    await _audit(
        db,
        request,
        current_user,
        "ai.model_selected",
        metadata={
            "execution_mode": record.execution_mode,
            "model_id": record.selected_model_id,
        },
    )
    return AiPreferences.model_validate(record, from_attributes=True)


@router.post("/context/preview", response_model=AiContextPreviewResponse)
async def ai_context_preview_endpoint(
    body: AiContextPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiContextPreviewResponse:
    _require_chat_role(current_user)
    items = await preview_knowledge_context(db, body.query, body.policy)
    return AiContextPreviewResponse(
        policy=body.policy,
        items=items,
        total_included=len(items),
        message="Only the excerpts selected here will be included in the next request.",
    )


@router.post("/models/test", response_model=AiModelTestResponse)
async def test_ai_model_endpoint(
    body: AiModelTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiModelTestResponse:
    _require_admin(current_user)
    preferences = await get_preferences(db, current_user.id)
    try:
        model = await require_allowed_model(
            get_adapter(), body.model_id, preferences.execution_mode
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not is_free_or_local(model):
        raise HTTPException(
            status_code=403,
            detail=(
                "Model test is limited to local or currently provider-reported "
                "free models."
            ),
        )
    adapter = get_adapter()
    prompt = (
        "Respond with READY and identify only the selected model ID. Do not use tools."
    )
    started = time.perf_counter()
    try:
        content = await _complete_test(adapter, model, prompt)
    except Exception:
        return AiModelTestResponse(
            available=False,
            model_id=model.id,
            error="The selected model did not complete the harmless test request.",
        )
    return AiModelTestResponse(
        available=True,
        latency_ms=round((time.perf_counter() - started) * 1000),
        model_id=model.id,
        response=sanitize_ai_text(content, max_chars=300),
    )


@router.get("/sessions", response_model=list[AiSessionView])
async def list_ai_sessions_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AiSessionView]:
    _require_chat_role(current_user)
    sessions = await list_user_sessions(db, current_user.id)
    return [await session_view(db, item) for item in sessions]


@router.post(
    "/sessions", response_model=AiSessionView, status_code=status.HTTP_201_CREATED
)
async def create_ai_session_endpoint(
    body: AiSessionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiSessionView:
    _require_chat_role(current_user)
    # Serialize per-owner creation so parallel requests cannot bypass the cap.
    await db.execute(
        select(User.id).where(User.id == current_user.id).with_for_update()
    )
    session_count = await db.scalar(
        select(func.count())
        .select_from(AiSession)
        .where(AiSession.owner_id == current_user.id)
    )
    session_limit = max(1, min(settings.AI_SESSION_MAX_SESSIONS, 500))
    if (session_count or 0) >= session_limit:
        raise HTTPException(
            status_code=409,
            detail=(
                "This account reached its AI session limit. Delete older sessions "
                "before starting another chat."
            ),
        )
    preferences = await get_preferences(db, current_user.id)
    try:
        model = await require_allowed_model(
            get_adapter(), body.model_id, preferences.execution_mode
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    external_session_id: str | None = None
    if model.provider_id not in {"ollama", "lmstudio"}:
        try:
            external_session_id = await get_adapter().create_session(
                "RavenTech AI chat"
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "OpenCode loopback server is unavailable. Start the optional "
                    "local server, then refresh providers."
                ),
            ) from exc
    session = AiSession(
        owner_id=current_user.id,
        title=sanitize_ai_text(body.title, max_chars=120) or "New AI chat",
        provider_id=model.provider_id,
        model_id=model.model_id,
        execution_type=execution_for_model(model),
        context_policy=body.context_policy,
        external_session_id=external_session_id,
    )
    db.add(session)
    await db.flush()
    await save_preferences(
        db,
        current_user.id,
        preferences.model_copy(update={"selected_model_id": model.id}),
    )
    await _audit(
        db,
        request,
        current_user,
        "ai.session_created",
        resource_id=session.id,
        metadata={
            "provider_id": model.provider_id,
            "model_id": model.model_id,
            "execution_type": session.execution_type,
        },
    )
    return await session_view(db, session)


@router.get("/sessions/{session_id}", response_model=AiSessionView)
async def get_ai_session_endpoint(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiSessionView:
    _require_chat_role(current_user)
    session = await get_user_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    return await session_view(db, session)


@router.patch("/sessions/{session_id}", response_model=AiSessionView)
async def rename_ai_session_endpoint(
    session_id: uuid.UUID,
    body: AiSessionRename,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiSessionView:
    _require_chat_role(current_user)
    session = await get_user_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    session.title = sanitize_ai_text(body.title, max_chars=120) or "AI chat"
    await db.flush()
    return await session_view(db, session)


@router.post("/sessions/{session_id}/archive", response_model=AiSessionView)
async def archive_ai_session_endpoint(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiSessionView:
    _require_chat_role(current_user)
    session = await get_user_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    if session.status == "running":
        raise HTTPException(
            status_code=409,
            detail=(
                "A running AI session cannot be archived. Cancel or wait for it first."
            ),
        )
    session.archived = True
    await db.flush()
    return await session_view(db, session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_session_endpoint(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_chat_role(current_user)
    session = await get_user_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    if session.status == "running":
        raise HTTPException(
            status_code=409,
            detail=(
                "A running AI session cannot be deleted. Cancel or wait for it first."
            ),
        )
    await db.delete(session)
    if session.external_session_id:
        await get_adapter().close_session(session.external_session_id)
    await _audit(
        db, request, current_user, "ai.session_deleted", resource_id=session_id
    )


@router.post("/sessions/{session_id}/messages", response_model=AiMessageResult)
async def send_ai_message_endpoint(
    session_id: uuid.UUID,
    body: AiMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiMessageResult:
    _require_chat_role(current_user)
    try:
        _validate_requested_workflow(body.workflow, body.workflow_scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    session_result = await db.execute(
        select(AiSession)
        .where(AiSession.id == session_id, AiSession.owner_id == current_user.id)
        .with_for_update()
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    if session.status == "running":
        raise HTTPException(
            status_code=409,
            detail="This AI session already has a response in progress.",
        )
    count_result = await db.execute(
        select(func.count(AiMessage.id)).where(AiMessage.session_id == session.id)
    )
    if int(count_result.scalar_one()) >= max(
        20, min(settings.AI_SESSION_MAX_MESSAGES, 200)
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This AI session reached its message limit. Start a new session "
                "or delete this one."
            ),
        )
    preferences = await get_preferences(db, current_user.id)
    model_ref = f"{session.provider_id}/{session.model_id}"
    try:
        model = await require_allowed_model(
            get_adapter(), model_ref, preferences.execution_mode
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    policy = body.context_policy
    sources = await load_selected_context(db, body.knowledge_citation_ids, policy)
    content = sanitize_ai_text(body.content, max_chars=settings.AI_MESSAGE_MAX_CHARS)
    if not content:
        raise HTTPException(
            status_code=422, detail="Message was empty after sensitive-value filtering."
        )
    user_message = AiMessage(
        session_id=session.id,
        sequence=await next_message_sequence(db, session.id),
        role="user",
        content=content,
        provider_id=model.provider_id,
        model_id=model.model_id,
        execution_type=session.execution_type,
        context_sources=[
            {
                "citation_id": item.citation_id,
                "title": item.title,
                "source": item.source,
            }
            for item in sources
        ],
        supplied_citations=[item.citation_id for item in sources],
    )
    db.add(user_message)
    session.context_policy = policy
    session.status = "running"
    await db.flush()
    await _audit(
        db,
        request,
        current_user,
        "ai.message_requested",
        resource_id=session.id,
        metadata={
            "provider_id": model.provider_id,
            "model_id": model.model_id,
            "execution_type": session.execution_type,
            "context_source_count": len(sources),
            "workflow": body.workflow,
            "remote_tool_evidence_consent": bool(
                body.allow_remote_tool_context and model.remote and not model.local
            ),
        },
    )
    await db.commit()
    try:
        assistant_content, tool_results = await _run_ai_turn(
            db, request, current_user, session, model, content, sources, body
        )
        _attach_tool_evidence(user_message, tool_results)
        await db.refresh(session)
        assistant_status = "completed"
        if session.status == "cancelled":
            assistant_content = "Generation cancelled."
            assistant_status = "cancelled"
        assistant_content = sanitize_ai_text(assistant_content, max_chars=20_000)
        assistant = AiMessage(
            session_id=session.id,
            sequence=await next_message_sequence(db, session.id),
            role="assistant",
            content=assistant_content,
            status=assistant_status,
            provider_id=model.provider_id,
            model_id=model.model_id,
            execution_type=session.execution_type,
            context_sources=user_message.context_sources,
            supplied_citations=user_message.supplied_citations,
        )
        db.add(assistant)
        if session.status != "cancelled":
            session.status = "ready"
        await _audit(
            db,
            request,
            current_user,
            "ai.message_completed",
            resource_id=session.id,
            metadata={
                "provider_id": model.provider_id,
                "model_id": model.model_id,
                "execution_type": session.execution_type,
                "response_sha256": hashlib.sha256(
                    assistant_content.encode("utf-8")
                ).hexdigest(),
            },
        )
        await db.flush()
        await db.refresh(session)
        completed_view = await session_view(db, session)
        return AiMessageResult(
            session_id=session.id,
            user_message=completed_view.messages[-2],
            assistant_message=completed_view.messages[-1],
            sources=sources,
        )
    except Exception as exc:
        await db.refresh(session)
        if session.status != "cancelled":
            session.status = "failed"
        await _audit(
            db,
            request,
            current_user,
            "ai.message_failed",
            resource_id=session.id,
            metadata={
                "provider_id": model.provider_id,
                "model_id": model.model_id,
                "error_category": _safe_error_category(exc),
            },
        )
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=(
                "The selected AI provider did not complete the request. Core "
                "RavenTech services remain available."
            ),
        ) from None


@router.post("/sessions/{session_id}/messages/stream")
async def stream_ai_message_endpoint(
    session_id: uuid.UUID,
    body: AiMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _require_chat_role(current_user)
    session_result = await db.execute(
        select(AiSession)
        .where(AiSession.id == session_id, AiSession.owner_id == current_user.id)
        .with_for_update()
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    if session.status == "running":
        raise HTTPException(
            status_code=409, detail="An AI response is already running."
        )
    count = int(
        (
            await db.execute(
                select(func.count(AiMessage.id)).where(
                    AiMessage.session_id == session.id
                )
            )
        ).scalar_one()
    )
    if count >= max(20, min(settings.AI_SESSION_MAX_MESSAGES, 200)):
        raise HTTPException(
            status_code=409, detail="This AI session reached its message limit."
        )
    preferences = await get_preferences(db, current_user.id)
    model_ref = f"{session.provider_id}/{session.model_id}"
    try:
        model = await require_allowed_model(
            get_adapter(), model_ref, preferences.execution_mode
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    sources = await load_selected_context(
        db, body.knowledge_citation_ids, body.context_policy
    )
    try:
        _validate_requested_workflow(body.workflow, body.workflow_scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    content = sanitize_ai_text(body.content, max_chars=settings.AI_MESSAGE_MAX_CHARS)
    if not content:
        raise HTTPException(
            status_code=422, detail="Message was empty after sensitive-value filtering."
        )
    user_message = AiMessage(
        session_id=session.id,
        sequence=await next_message_sequence(db, session.id),
        role="user",
        content=content,
        provider_id=model.provider_id,
        model_id=model.model_id,
        execution_type=session.execution_type,
        context_sources=[
            {
                "citation_id": item.citation_id,
                "title": item.title,
                "source": item.source,
            }
            for item in sources
        ],
        supplied_citations=[item.citation_id for item in sources],
    )
    db.add(user_message)
    session.context_policy = body.context_policy
    session.status = "running"
    await db.flush()
    await _audit(
        db,
        request,
        current_user,
        "ai.message_requested",
        resource_id=session.id,
        metadata={
            "provider_id": model.provider_id,
            "model_id": model.model_id,
            "execution_type": session.execution_type,
            "context_source_count": len(sources),
            "streaming": True,
        },
    )
    await db.commit()
    cancellation = asyncio.Event()
    _ACTIVE_STREAMS[session.id] = cancellation
    adapter = get_adapter()

    async def generate() -> AsyncIterator[str]:
        stream_sanitizer = AiStreamSanitizer(max_chars=20_000)
        finished = False
        try:
            use_tool_turn = body.workflow is not None or (
                model.supports_tools is True
                and (not model.remote or model.local or body.allow_remote_tool_context)
            )
            if use_tool_turn:
                final_text, tool_results = await _run_ai_turn(
                    db,
                    request,
                    current_user,
                    session,
                    model,
                    content,
                    sources,
                    body,
                    cancel_event=cancellation,
                )
                _attach_tool_evidence(user_message, tool_results)
                if cancellation.is_set():
                    final_text = "Generation cancelled."
                stream_sanitizer = AiStreamSanitizer(max_chars=20_000)
                for offset in range(0, len(final_text), 240):
                    if cancellation.is_set():
                        break
                    safe_chunk = stream_sanitizer.feed(
                        final_text[offset : offset + 240]
                    )
                    if safe_chunk:
                        yield _sse("delta", {"text": safe_chunk})
                final_delta, sanitized_output = stream_sanitizer.finish()
                if final_delta:
                    yield _sse("delta", {"text": final_delta})
                await db.refresh(session)
                cancelled = cancellation.is_set() or session.status == "cancelled"
                final_text = sanitize_ai_text(sanitized_output, max_chars=20_000)
                if cancelled and not final_text:
                    final_text = "Generation cancelled."
                assistant = AiMessage(
                    session_id=session.id,
                    sequence=await next_message_sequence(db, session.id),
                    role="assistant",
                    content=final_text,
                    status="cancelled" if cancelled else "completed",
                    provider_id=model.provider_id,
                    model_id=model.model_id,
                    execution_type=session.execution_type,
                    context_sources=user_message.context_sources,
                    supplied_citations=user_message.supplied_citations,
                )
                db.add(assistant)
                session.status = "cancelled" if cancelled else "ready"
                await _audit(
                    db,
                    request,
                    current_user,
                    "ai.message_cancelled" if cancelled else "ai.message_completed",
                    resource_id=session.id,
                    metadata={
                        "provider_id": model.provider_id,
                        "model_id": model.model_id,
                        "execution_type": session.execution_type,
                        "response_sha256": hashlib.sha256(
                            final_text.encode("utf-8")
                        ).hexdigest(),
                        "tool_count": len(tool_results),
                    },
                )
                await db.commit()
                finished = True
                yield _sse(
                    "done",
                    {
                        "status": session.status,
                        "citations": user_message.supplied_citations,
                    },
                )
                return

            prompt = build_context_prompt(content, sources)
            if model.provider_id in {"ollama", "lmstudio"}:
                chunks = adapter.stream_local(
                    model.provider_id, model.model_id, prompt, cancellation
                )
            elif model.supports_streaming is False:

                async def final_chunk() -> AsyncIterator[str]:
                    yield await _complete_session(adapter, session, model, prompt)

                chunks = final_chunk()
            else:
                if not session.external_session_id:
                    session.external_session_id = await adapter.create_session(
                        "RavenTech AI chat"
                    )
                    await db.commit()
                chunks = adapter.stream_complete(
                    session.external_session_id,
                    model.provider_id,
                    model.model_id,
                    prompt,
                    cancellation,
                )
            async for chunk in chunks:
                if cancellation.is_set():
                    break
                safe_chunk = stream_sanitizer.feed(chunk)
                if not safe_chunk:
                    continue
                yield _sse("delta", {"text": safe_chunk})
            final_delta, sanitized_output = stream_sanitizer.finish()
            if final_delta:
                yield _sse("delta", {"text": final_delta})
            await db.refresh(session)
            cancelled = cancellation.is_set() or session.status == "cancelled"
            final_text = sanitize_ai_text(sanitized_output, max_chars=20_000)
            if not final_text and not cancelled:
                raise RuntimeError("provider returned no visible response")
            if cancelled and not final_text:
                final_text = "Generation cancelled."
            assistant = AiMessage(
                session_id=session.id,
                sequence=await next_message_sequence(db, session.id),
                role="assistant",
                content=final_text,
                status="cancelled" if cancelled else "completed",
                provider_id=model.provider_id,
                model_id=model.model_id,
                execution_type=session.execution_type,
                context_sources=user_message.context_sources,
                supplied_citations=user_message.supplied_citations,
            )
            db.add(assistant)
            session.status = "cancelled" if cancelled else "ready"
            action = "ai.message_cancelled" if cancelled else "ai.message_completed"
            await _audit(
                db,
                request,
                current_user,
                action,
                resource_id=session.id,
                metadata={
                    "provider_id": model.provider_id,
                    "model_id": model.model_id,
                    "execution_type": session.execution_type,
                    "response_sha256": hashlib.sha256(
                        final_text.encode("utf-8")
                    ).hexdigest(),
                },
            )
            await db.commit()
            finished = True
            yield _sse(
                "done",
                {
                    "status": session.status,
                    "citations": user_message.supplied_citations,
                },
            )
        except asyncio.CancelledError:
            cancellation.set()
            if session.external_session_id:
                await adapter.cancel(session.external_session_id)
            raise
        except Exception as exc:
            await db.refresh(session)
            if session.status != "cancelled":
                session.status = "failed"
            await _audit(
                db,
                request,
                current_user,
                "ai.message_failed",
                resource_id=session.id,
                metadata={
                    "provider_id": model.provider_id,
                    "model_id": model.model_id,
                    "error_category": _safe_error_category(exc),
                    "streaming": True,
                },
            )
            await db.commit()
            yield _sse(
                "error",
                {"message": "The selected AI provider did not complete the request."},
            )
        finally:
            if not finished and session.status == "running":
                session.status = "cancelled"
                await db.commit()
            _ACTIVE_STREAMS.pop(session.id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_ai_session_endpoint(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    _require_chat_role(current_user)
    session = await get_user_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found.")
    if session.status != "running":
        return {"cancelled": False}
    cancellation = _ACTIVE_STREAMS.get(session.id)
    if cancellation:
        cancellation.set()
    session.status = "cancelled"
    await _audit(
        db, request, current_user, "ai.message_cancelled", resource_id=session.id
    )
    await db.commit()
    provider_cancelled = False
    if session.external_session_id:
        provider_cancelled = await get_adapter().cancel(session.external_session_id)
    return {"cancelled": True, "provider_cancelled": provider_cancelled}


@router.post("/prompt-handoff", response_model=AiPromptHandoffResponse)
async def create_prompt_handoff_endpoint(
    body: AiPromptHandoffRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiPromptHandoffResponse:
    _require_chat_role(current_user)
    try:
        prompt, command, digest = build_prompt_handoff(
            kind=body.kind,
            title=body.title,
            facts=body.facts,
            citations=body.citations,
            model_id=body.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    citations = [sanitize_ai_text(item, max_chars=180) for item in body.citations[:20]]
    await _audit(
        db,
        request,
        current_user,
        "ai.prompt_handoff.generated",
        metadata={
            "kind": body.kind,
            "citation_count": len(citations),
            "content_sha256": digest,
        },
    )
    return AiPromptHandoffResponse(
        prompt=prompt, command=command, citations=citations, content_hash=digest
    )


@router.post("/prompt-handoff/copied", status_code=status.HTTP_204_NO_CONTENT)
async def audit_prompt_handoff_copy_endpoint(
    body: AiPromptCopyAuditRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_chat_role(current_user)
    digest = body.content_hash
    if len(digest) != 64 or any(
        char not in "0123456789abcdef" for char in digest.casefold()
    ):
        raise HTTPException(
            status_code=422, detail="Prompt handoff reference is invalid."
        )
    await _audit(
        db,
        request,
        current_user,
        "ai.prompt_copied",
        metadata={"content_sha256": digest.lower(), "content_type": body.content_type},
    )


async def _catalog(
    adapter: OpenCodeAdapter,
    *,
    refresh: bool,
    preferences: AiPreferences | None = None,
) -> AiCatalogResponse:
    runtime = await adapter.get_runtime()
    providers, models = await adapter.discover(refresh=refresh)
    return AiCatalogResponse(
        runtime=AiRuntimeStatus.model_validate(runtime),
        providers=[AiProvider.model_validate(item) for item in providers],
        models=[model_view(item) for item in models],
        refreshed_at=datetime.now(UTC),
        warning=None
        if runtime.get("available") or any(item.local for item in models)
        else (
            "OpenCode and local model runtimes are optional and currently unavailable."
        ),
        recommended_model_id=_recommended_model_id(models, preferences),
    )


def _recommended_model_id(
    models: list[ModelRecord], preferences: AiPreferences | None
) -> str | None:
    prefs = preferences or AiPreferences()
    if prefs.selected_model_id:
        selected = next(
            (item for item in models if item.id == prefs.selected_model_id), None
        )
        if selected is None or not selected.available:
            return None
        return (
            selected.id
            if _model_allowed_by_mode(selected, prefs.execution_mode)
            else None
        )
    candidates: list[str | None] = [prefs.preferred_local_model_id]
    candidates.extend(item.id for item in models if item.local and item.available)
    if prefs.execution_mode != "local_only":
        candidates.append(prefs.preferred_free_model_id)
        candidates.extend(
            item.id
            for item in models
            if item.available and item.free_status == "provider_reported_free"
        )
    for candidate in candidates:
        if not candidate:
            continue
        model = next(
            (item for item in models if item.id == candidate and item.available), None
        )
        if model is not None and _model_allowed_by_mode(model, prefs.execution_mode):
            return model.id
    return None


def _model_allowed_by_mode(model: ModelRecord, execution_mode: str) -> bool:
    if execution_mode == "local_only":
        return model.local
    if execution_mode == "free_only":
        return model.local or model.free_status == "provider_reported_free"
    return True


async def _complete_test(
    adapter: OpenCodeAdapter, model: ModelRecord, prompt: str
) -> str:
    provider_id = model.provider_id
    model_id = model.model_id
    if provider_id in {"ollama", "lmstudio"}:
        return await adapter.complete_local(provider_id, model_id, prompt)
    external_id = await adapter.create_session("RavenTech harmless model test")
    try:
        return await adapter.complete(external_id, provider_id, model_id, prompt)
    finally:
        await adapter.close_session(external_id)


async def _complete_session(
    adapter: OpenCodeAdapter, session: AiSession, model: ModelRecord, prompt: str
) -> str:
    provider_id = model.provider_id
    model_id = model.model_id
    if provider_id in {"ollama", "lmstudio"}:
        return await adapter.complete_local(provider_id, model_id, prompt)
    if not session.external_session_id:
        session.external_session_id = await adapter.create_session("RavenTech AI chat")
    return await adapter.complete(
        session.external_session_id, provider_id, model_id, prompt
    )


def _validate_requested_workflow(
    workflow: str | None, scope_id: uuid.UUID | None
) -> None:
    if workflow is None:
        return
    try:
        workflow_calls(workflow, scope_id)
    except ValueError as exc:
        raise ValueError(str(exc)) from None


async def _run_ai_turn(
    db: AsyncSession,
    request: Request,
    user: User,
    session: AiSession,
    model: ModelRecord,
    content: str,
    sources: list[Any],
    body: AiMessageRequest,
    *,
    cancel_event: asyncio.Event | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    adapter = get_adapter()
    native_inventory: NativeInventory | None = None
    if body.desktop_inventory is not None:
        try:
            native_inventory = NativeInventory.model_validate(body.desktop_inventory)
        except Exception:
            native_inventory = None

    is_remote_model = model.remote and not model.local
    may_request_tools = body.workflow is not None or model.supports_tools is True
    if is_remote_model and may_request_tools and not body.allow_remote_tool_context:
        response = await _complete_session(
            adapter, session, model, build_context_prompt(content, sources)
        )
        return response, []

    if body.workflow is not None:
        calls = workflow_calls(body.workflow, body.workflow_scope_id)
        results = await execute_model_tool_calls(
            db,
            user,
            calls,
            native_inventory=native_inventory,
            request=request,
            session_id=session.id,
            redis=getattr(request.app.state, "redis", None),
            cancel_event=cancel_event,
        )
        if cancel_event is not None and cancel_event.is_set():
            return "Generation cancelled.", results
        prompt = build_evidence_followup(content, results)
        return await _complete_session(adapter, session, model, prompt), results

    prepared_prompt = build_context_prompt(content, sources)
    if model.supports_tools is not True:
        return await _complete_session(adapter, session, model, prepared_prompt), []

    first_response = await _complete_session(
        adapter, session, model, build_tool_aware_prompt(content, sources, user)
    )
    request_data = parse_model_tool_request(first_response)
    if request_data is None:
        if "<raventech_tool_request>" in first_response.casefold():
            return (
                "The model returned an invalid RavenTech tool request. "
                "No tool was executed.",
                [],
            )
        return first_response, []
    results = await execute_model_tool_calls(
        db,
        user,
        request_data.tool_calls,
        native_inventory=native_inventory,
        request=request,
        session_id=session.id,
        redis=getattr(request.app.state, "redis", None),
        cancel_event=cancel_event,
    )
    if cancel_event is not None and cancel_event.is_set():
        return "Generation cancelled.", results
    final_response = await _complete_session(
        adapter, session, model, build_evidence_followup(content, results)
    )
    if parse_model_tool_request(final_response) is not None:
        final_response = (
            "The RavenTech read-only tool request limit was reached. The evidence "
            "returned in this turn is shown below; no additional request was executed."
        )
    return final_response, results


def _attach_tool_evidence(
    message: AiMessage, tool_results: list[dict[str, Any]]
) -> None:
    sources = list(message.context_sources or [])
    citations = list(message.supplied_citations or [])
    for result in tool_results:
        tool_id = str(result.get("tool", "raventech"))[:100]
        evidence_references: list[dict[str, Any]] = []
        for item in result.get("evidence", [])[:10]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            raw_scope = item.get("scope")
            scope: dict[str, str] = {}
            if isinstance(raw_scope, dict):
                scope_type = raw_scope.get("type")
                if isinstance(scope_type, str) and scope_type in {
                    "primary_host",
                    "global",
                    "investigation",
                    "lan_asset",
                }:
                    scope["type"] = str(scope_type)
                for key in ("investigation_id", "asset_id", "alert_id"):
                    raw_id = raw_scope.get(key)
                    if isinstance(raw_id, str):
                        try:
                            scope[key] = str(uuid.UUID(raw_id))
                        except ValueError:
                            continue
            reference = {
                "id": sanitize_tool_text(str(item.get("id", "")), max_chars=160),
                "source_type": sanitize_tool_text(
                    str(item.get("source_type", "unknown")), max_chars=80
                ),
                "timestamp": sanitize_tool_text(
                    str(item.get("timestamp", "")), max_chars=40
                ) or None,
                "freshness": sanitize_tool_text(
                    str(item.get("freshness", "unknown")), max_chars=48
                ),
                "confidence": sanitize_tool_text(
                    str(item.get("confidence", "unknown")), max_chars=24
                ),
                "scope": scope,
            }
            evidence_references.append(reference)
        evidence_ids = [item["id"] for item in evidence_references]
        sources.append(
            {
                "kind": "tool_activity",
                "tool_id": tool_id,
                "success": bool(result.get("success")),
                "evidence_ids": evidence_ids,
                "evidence_references": evidence_references,
                "safe_error_code": result.get("safe_error_code"),
            }
        )
        citations.extend(evidence_ids)
    message.context_sources = sources[:100]
    message.supplied_citations = list(dict.fromkeys(citations))[:100]


async def _audit(
    db: AsyncSession,
    request: Request,
    user: User,
    action: str,
    *,
    resource_id: uuid.UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="ai_session" if resource_id else "ai_gateway",
        resource_id=resource_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata=metadata,
    )


def _require_chat_role(user: User) -> None:
    if user.role not in _CHAT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="AI chat is available to analysts and administrators.",
        )


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access is required to test a provider model.",
        )


def _safe_error_category(exc: Exception) -> str:
    message = str(exc).casefold()
    if "timeout" in message:
        return "timeout"
    if "connect" in message or "unavailable" in message:
        return "provider_unavailable"
    return "provider_failed"


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
