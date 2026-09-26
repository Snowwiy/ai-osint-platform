from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.action_gateway import (
    ActionApproval,
    ActionGatewayPolicy,
    ActionProposal,
)
from app.models.user import User
from app.schemas.action_gateway import (
    ActionApprovalRequest,
    ActionCapabilities,
    ActionCapability,
    ActionGatewayPolicyUpdate,
    ActionGatewayPolicyView,
    ActionProposalCreate,
    ActionProposalList,
    ActionProposalView,
    LocalActionClaimRequest,
    LocalActionClaimResponse,
    LocalActionCompletion,
    LocalActionPreviewResponse,
)
from app.services.action_gateway import (
    ActionGatewayError,
    approve_proposal,
    claim_local_execution,
    complete_local_execution,
    create_proposal,
    execute_backend_action,
    list_proposals,
    proposal_view,
    reject_proposal,
    set_gateway_enabled,
)
from app.services.action_registry import ACTION_REGISTRY

router = APIRouter(prefix="/actions", tags=["human-approved actions"])


def _raise(exc: ActionGatewayError) -> NoReturn:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


async def _get_owned_proposal(
    db: AsyncSession, user: User, proposal_id: uuid.UUID
) -> ActionProposal:
    proposal = (
        await db.execute(select(ActionProposal).where(ActionProposal.id == proposal_id))
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "proposal_not_found",
                "message": "Action proposal was not found.",
            },
        )
    if user.role != "admin" and proposal.requested_by_user_id != user.id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "proposal_not_found",
                "message": "Action proposal was not found.",
            },
        )
    return proposal


@router.get("/capabilities", response_model=ActionCapabilities)
async def action_capabilities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionCapabilities:
    policy = await db.get(ActionGatewayPolicy, 1)
    enabled = policy.enabled if policy is not None else True
    from app.services.ai.tool_gateway import (
        registered_action_proposal_tools,
        registered_tools,
    )

    tools = registered_tools(current_user)
    proposal_tools = await registered_action_proposal_tools(db, current_user)
    items = [
        ActionCapability(
            action_id=definition.action_id,
            display_name=definition.display_name,
            description=definition.description,
            risk_level=definition.risk_level,
            required_role=definition.required_role,
            executor=definition.executor,
        )
        for definition in ACTION_REGISTRY.values()
        if current_user.role == "admin" or definition.required_role == "analyst"
    ]
    return ActionCapabilities(
        enabled=enabled,
        can_manage_policy=current_user.role == "admin",
        actions=items,
        read_tools=len(tools),
        action_proposal_tools=len(proposal_tools),
    )


@router.get("/policy", response_model=ActionGatewayPolicyView)
async def action_policy(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ActionGatewayPolicyView:
    row = await db.get(ActionGatewayPolicy, 1)
    return ActionGatewayPolicyView(
        enabled=row.enabled if row is not None else True,
        updated_by_user_id=row.updated_by_user_id if row else None,
        updated_at=row.updated_at if row else None,
    )


@router.patch("/policy", response_model=ActionGatewayPolicyView)
async def update_action_policy(
    body: ActionGatewayPolicyUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ActionGatewayPolicyView:
    row = await set_gateway_enabled(db, current_user, body.enabled)
    return ActionGatewayPolicyView(
        enabled=row.enabled,
        updated_by_user_id=row.updated_by_user_id,
        updated_at=row.updated_at,
    )


@router.get("/proposals", response_model=ActionProposalList)
async def action_proposals(
    proposal_status: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalList:
    rows = await list_proposals(db, current_user, status=proposal_status, limit=limit)
    policy = await db.get(ActionGatewayPolicy, 1)
    return ActionProposalList(
        items=[
            ActionProposalView.model_validate(await proposal_view(db, row))
            for row in rows
        ],
        total=len(rows),
        enabled=policy.enabled if policy else True,
    )


@router.post(
    "/proposals", response_model=ActionProposalView, status_code=status.HTTP_201_CREATED
)
async def create_action_proposal(
    body: ActionProposalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalView:
    try:
        proposal = await create_proposal(db, current_user, body)
        return ActionProposalView.model_validate(await proposal_view(db, proposal))
    except ActionGatewayError as exc:
        _raise(exc)


@router.get("/proposals/{proposal_id}", response_model=ActionProposalView)
async def get_action_proposal(
    proposal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalView:
    proposal = await _get_owned_proposal(db, current_user, proposal_id)
    return ActionProposalView.model_validate(await proposal_view(db, proposal))


@router.post("/proposals/{proposal_id}/approve", response_model=ActionProposalView)
async def approve_action_proposal(
    proposal_id: uuid.UUID,
    body: ActionApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalView:
    try:
        proposal, _approval = await approve_proposal(
            db,
            current_user,
            proposal_id,
            body.confirmation_text,
            body.current_snapshot,
        )
        return ActionProposalView.model_validate(await proposal_view(db, proposal))
    except ActionGatewayError as exc:
        _raise(exc)


@router.post("/proposals/{proposal_id}/reject", response_model=ActionProposalView)
async def reject_action_proposal(
    proposal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalView:
    try:
        proposal = await reject_proposal(db, current_user, proposal_id)
        return ActionProposalView.model_validate(await proposal_view(db, proposal))
    except ActionGatewayError as exc:
        _raise(exc)


@router.post("/proposals/{proposal_id}/execute", response_model=ActionProposalView)
async def execute_action_proposal(
    proposal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalView:
    try:
        proposal = await execute_backend_action(db, current_user, proposal_id)
        return ActionProposalView.model_validate(await proposal_view(db, proposal))
    except ActionGatewayError as exc:
        _raise(exc)


@router.post(
    "/proposals/{proposal_id}/claim-local", response_model=LocalActionClaimResponse
)
async def claim_local_action(
    proposal_id: uuid.UUID,
    body: LocalActionClaimRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LocalActionClaimResponse:
    try:
        proposal, _approval = await claim_local_execution(
            db, current_user, proposal_id, body.current_snapshot
        )
        expected = (
            "terminated"
            if proposal.action_id == "raventech.process.terminate"
            else {"start": "running", "stop": "stopped", "restart": "running"}[
                proposal.action_id.rsplit(".", 1)[-1]
            ]
        )
        return LocalActionClaimResponse(
            proposal_id=proposal.id,
            action_id=proposal.action_id,
            target_id=proposal.target_id or "",
            target_display_name=proposal.target_display_name,
            parameters=proposal.parameters,
            target_snapshot=proposal.target_snapshot,
            expected_result=expected,
        )
    except ActionGatewayError as exc:
        _raise(exc)


@router.get(
    "/proposals/{proposal_id}/native-preview", response_model=LocalActionPreviewResponse
)
async def preview_local_action(
    proposal_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LocalActionPreviewResponse:
    proposal = await _get_owned_proposal(db, current_user, proposal_id)
    approval = (
        await db.execute(
            select(ActionApproval).where(ActionApproval.proposal_id == proposal.id)
        )
    ).scalar_one_or_none()
    if (
        proposal.status != "approved"
        or approval is None
        or approval.consumed_at is not None
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approval_unavailable",
                "message": "A fresh unused human approval is required.",
            },
        )
    if proposal.expires_at <= datetime.now(UTC) or approval.expires_at <= datetime.now(
        UTC
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approval_expired",
                "message": "Approval expired; create and review a new proposal.",
            },
        )
    if (
        proposal.action_id not in ACTION_REGISTRY
        or ACTION_REGISTRY[proposal.action_id].executor != "desktop_native"
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "unsupported_action",
                "message": (
                    "This action is not available to the local desktop provider."
                ),
            },
        )
    expected = (
        "terminated"
        if proposal.action_id == "raventech.process.terminate"
        else {"start": "running", "stop": "stopped", "restart": "running"}[
            proposal.action_id.rsplit(".", 1)[-1]
        ]
    )
    return LocalActionPreviewResponse(
        proposal_id=proposal.id,
        action_id=proposal.action_id,
        target_id=proposal.target_id or "",
        target_display_name=proposal.target_display_name,
        parameters=proposal.parameters,
        target_snapshot=proposal.target_snapshot,
        expected_result=expected,
    )


@router.post(
    "/proposals/{proposal_id}/complete-local", response_model=ActionProposalView
)
async def complete_local_action(
    proposal_id: uuid.UUID,
    body: LocalActionCompletion,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalView:
    try:
        proposal = await complete_local_execution(
            db,
            current_user,
            proposal_id,
            success=body.success,
            observed_state=body.observed_state,
            safe_error_code=body.safe_error_code,
        )
        return ActionProposalView.model_validate(await proposal_view(db, proposal))
    except ActionGatewayError as exc:
        _raise(exc)
