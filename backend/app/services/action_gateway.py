from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.action_gateway import (
    ActionApproval,
    ActionGatewayPolicy,
    ActionProposal,
    ActionTargetLock,
)
from app.models.audit_log import AuditLog
from app.models.background_job import BackgroundJob, BackgroundJobEvent
from app.models.lan_monitoring import LanAsset
from app.models.monitoring_history import MonitoringChangeEvent
from app.models.notification import Notification
from app.models.user import User
from app.schemas.action_gateway import ActionProposalCreate
from app.schemas.lan_monitoring import LanAssetUpdate
from app.services.action_registry import ACTION_REGISTRY, ActionDefinition

PROPOSAL_TTL = timedelta(minutes=10)
APPROVAL_TTL = timedelta(seconds=120)
NATIVE_ACTION_LOCK_TTL = timedelta(minutes=2)
MAX_ACTIVE_PER_USER = 20
SERVICE_NAME = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")
_SECRET_TEXT = re.compile(
    r"(?i)(?:bearer\s+\S+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"(?:password|passwd|secret|token|api[_-]?key|credential)\s*[:=])"
)
_PROTECTED_SERVICES = {
    "rpcss",
    "dcomlaunch",
    "rpceptmapper",
    "eventlog",
    "plugplay",
    "samss",
    "windefend",
    "mpssvc",
    "trustedinstaller",
    "winmgmt",
    "schedule",
    "lanmanworkstation",
    "lanmanserver",
    "profsvc",
    "cryptsvc",
    "gpsvc",
    "systemd",
    "dbus",
    "networkmanager",
    "networking",
    "sshd",
    "systemd-logind",
    "display-manager",
    "raventech-postgresql",
    "raventech-backend",
    "raventech-worker",
}
_PROTECTED_PROCESSES = {
    "system",
    "registry",
    "smss",
    "csrss",
    "wininit",
    "services",
    "lsass",
    "winlogon",
    "secure system",
    "dwm",
    "fontdrvhost",
    "memory compression",
    "svchost",
    "sihost",
    "explorer",
    "taskhostw",
    "raventech-osint-desktop",
    "systemd",
    "init",
    "kthreadd",
    "raventech-backend",
    "raventech-worker",
}
_RETRYABLE_JOB_TYPES = {
    "monitoring.refresh",
    "monitoring.lan_discovery",
    "monitoring.service_observation",
    "monitoring.service_observation.asset",
    "posture.recompute",
    "recommendations.recompute",
    "knowledge.source.sync",
}


class ActionGatewayError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def proposal_content_hash(proposal: ActionProposal) -> str:
    return canonical_hash(
        {
            "action_id": proposal.action_id,
            "requested_by_user_id": str(proposal.requested_by_user_id),
            "origin": proposal.origin,
            "scope_type": proposal.scope_type,
            "scope_id": proposal.scope_id,
            "target_type": proposal.target_type,
            "target_id": proposal.target_id,
            "target_display_name": proposal.target_display_name,
            "parameters": proposal.parameters,
            "reason": proposal.reason,
            "supporting_evidence_ids": proposal.supporting_evidence_ids,
            "risk_level": proposal.risk_level,
            "expected_effect": proposal.expected_effect,
            "possible_impact": proposal.possible_impact,
            "rollback_guidance": proposal.rollback_guidance,
            "preconditions": proposal.preconditions,
            "target_snapshot": proposal.target_snapshot,
            "expires_at": proposal.expires_at.isoformat(),
        }
    )


def _target_lock_key(proposal: ActionProposal) -> str:
    identity: Any = proposal.target_id
    if proposal.target_type == "local_process":
        identity = {
            "pid": proposal.target_snapshot.get("pid"),
            "creation_ticks": proposal.target_snapshot.get("creation_ticks"),
        }
    elif proposal.target_type == "local_service":
        identity = str(proposal.target_id or "").casefold()
    return canonical_hash(
        {
            "scope_type": proposal.scope_type,
            "scope_id": proposal.scope_id,
            "target_type": proposal.target_type,
            "identity": identity,
        }
    )


async def _acquire_native_target_lock(
    db: AsyncSession, proposal: ActionProposal, now: datetime
) -> None:
    target_key = _target_lock_key(proposal)
    statement = (
        pg_insert(ActionTargetLock)
        .values(
            target_key=target_key,
            proposal_id=proposal.id,
            lease_expires_at=now + NATIVE_ACTION_LOCK_TTL,
        )
        .on_conflict_do_update(
            index_elements=[ActionTargetLock.target_key],
            set_={
                "proposal_id": proposal.id,
                "lease_expires_at": now + NATIVE_ACTION_LOCK_TTL,
                "created_at": now,
            },
            where=ActionTargetLock.lease_expires_at <= now,
        )
        .returning(ActionTargetLock.target_key)
    )
    acquired = (await db.execute(statement)).scalar_one_or_none()
    if acquired is None:
        raise ActionGatewayError(
            "target_conflict",
            "Another approved action is currently executing for this target.",
            409,
        )


async def _release_native_target_lock(
    db: AsyncSession, proposal: ActionProposal
) -> None:
    await db.execute(
        delete(ActionTargetLock).where(
            ActionTargetLock.target_key == _target_lock_key(proposal),
            ActionTargetLock.proposal_id == proposal.id,
        )
    )


def approval_phrase(action_id: str, target: str) -> str:
    if action_id == "raventech.process.terminate":
        return f"TERMINATE {target}"
    if action_id == "raventech.service.stop":
        return f"STOP {target}"
    return f"APPROVE {target}"


def _check_text(value: str, *, limit: int) -> str:
    clean = " ".join(value.split()).strip()
    if not clean or len(clean) > limit or _SECRET_TEXT.search(clean):
        raise ActionGatewayError(
            "invalid_action_text",
            "Action text is empty, too long, or contains sensitive material.",
            422,
        )
    return clean


def _check_role(user: User, definition: ActionDefinition) -> None:
    allowed = (
        {"admin", "analyst"} if definition.required_role == "analyst" else {"admin"}
    )
    if user.role not in allowed:
        raise ActionGatewayError(
            "authorization_denied", "Your role cannot request this action.", 403
        )


def _parameters(definition: ActionDefinition, values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ActionGatewayError(
            "invalid_parameters", "Action parameters must be an object.", 422
        )
    action_id = definition.action_id
    if action_id in {"raventech.lan.services.refresh", "raventech.posture.recompute"}:
        if set(values) != {"asset_id"}:
            raise ActionGatewayError(
                "invalid_parameters", "A registered asset identifier is required.", 422
            )
        try:
            return {"asset_id": str(uuid.UUID(str(values["asset_id"])))}
        except (ValueError, TypeError) as exc:
            raise ActionGatewayError(
                "invalid_parameters", "A valid asset identifier is required.", 422
            ) from exc
    if action_id == "raventech.job.retry":
        if set(values) != {"job_id"}:
            raise ActionGatewayError(
                "invalid_parameters", "A registered job identifier is required.", 422
            )
        try:
            return {"job_id": str(uuid.UUID(str(values["job_id"])))}
        except (ValueError, TypeError) as exc:
            raise ActionGatewayError(
                "invalid_parameters", "A valid job identifier is required.", 422
            ) from exc
    if values:
        raise ActionGatewayError(
            "invalid_parameters", "This fixed action accepts no parameters.", 422
        )
    return {}


def _local_snapshot(
    definition: ActionDefinition, value: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ActionGatewayError(
            "invalid_target", "A native local inventory snapshot is required.", 422
        )
    if definition.target_type == "local_service":
        allowed = {
            "name",
            "display_name",
            "state",
            "pid",
            "start_type",
            "action_available",
        }
        if set(value) != allowed:
            raise ActionGatewayError(
                "invalid_target", "Local service identity is incomplete.", 422
            )
        name = value.get("name")
        display = value.get("display_name")
        state = value.get("state")
        if (
            not isinstance(name, str)
            or not SERVICE_NAME.fullmatch(name)
            or not isinstance(display, str)
            or not display.strip()
        ):
            raise ActionGatewayError(
                "invalid_target", "Local service identity is invalid.", 422
            )
        if state not in {
            "running",
            "stopped",
            "starting",
            "stopping",
            "paused",
            "unknown",
        }:
            raise ActionGatewayError(
                "invalid_target", "Local service state is invalid.", 422
            )
        if value.get("action_available") is not True:
            raise ActionGatewayError(
                "protected_target",
                "The local service is protected or not actionable.",
                403,
            )
        if name.casefold() in _PROTECTED_SERVICES:
            raise ActionGatewayError(
                "protected_target",
                "This system or RavenTech service is protected.",
                403,
            )
        expected = {"start": "stopped", "stop": "running", "restart": "running"}[
            definition.action_id.rsplit(".", 1)[-1]
        ]
        if state != expected:
            raise ActionGatewayError(
                "precondition_failed",
                f"The service must be {expected} before this action.",
                409,
            )
        return {
            "name": name,
            "display_name": display.strip()[:180],
            "state": state,
            "pid": value.get("pid") if isinstance(value.get("pid"), int) else None,
            "start_type": str(value.get("start_type") or "unknown")[:40],
            "action_available": True,
        }
    allowed = {"pid", "name", "started_at_unix", "creation_ticks", "action_available"}
    if set(value) != allowed:
        raise ActionGatewayError(
            "invalid_target", "Local process identity is incomplete.", 422
        )
    pid, name = value.get("pid"), value.get("name")
    ticks = value.get("creation_ticks")
    started = value.get("started_at_unix")
    if (
        not isinstance(pid, int)
        or pid <= 4
        or not isinstance(name, str)
        or not name.strip()
    ):
        raise ActionGatewayError(
            "invalid_target", "Local process identity is invalid.", 422
        )
    stem = name.casefold().removesuffix(".exe")
    if stem in _PROTECTED_PROCESSES or pid == 1:
        raise ActionGatewayError(
            "protected_target", "This system or RavenTech process is protected.", 403
        )
    if value.get("action_available") is not True:
        raise ActionGatewayError(
            "protected_target",
            "The operating system marked this process protected or unavailable.",
            403,
        )
    if (
        not isinstance(ticks, str)
        or not ticks.isdigit()
        or not isinstance(started, int)
    ):
        raise ActionGatewayError(
            "invalid_target", "Process start identity is unavailable.", 422
        )
    return {
        "pid": pid,
        "name": name[:160],
        "started_at_unix": started,
        "creation_ticks": ticks,
        "action_available": True,
    }


async def _database_target(
    db: AsyncSession,
    user: User,
    definition: ActionDefinition,
    target_id: str | None,
    parameters: dict[str, Any],
    submitted: dict[str, Any],
) -> tuple[str, str | None, dict[str, Any]]:
    action = definition.action_id
    if definition.target_type in {"local_service", "local_process"}:
        snapshot = _local_snapshot(definition, submitted)
        derived_id = (
            snapshot["name"]
            if definition.target_type == "local_service"
            else str(snapshot["pid"])
        )
        if target_id and target_id != derived_id:
            raise ActionGatewayError(
                "invalid_target",
                "Target identifier does not match the local inventory.",
                422,
            )
        return definition.target_type, derived_id, snapshot
    if action == "raventech.alert.acknowledge":
        try:
            alert_id = uuid.UUID(target_id or "")
        except ValueError as exc:
            raise ActionGatewayError(
                "invalid_target", "A valid alert identifier is required.", 422
            ) from exc
        row = await db.get(Notification, alert_id)
        if (
            row is None
            or row.notification_type != "monitoring_alert"
            or row.user_id not in (None, user.id)
        ):
            raise ActionGatewayError(
                "target_not_found", "The alert is unavailable to this user.", 404
            )
        if row.status != "unread":
            raise ActionGatewayError(
                "precondition_failed",
                "The alert is no longer awaiting acknowledgement.",
                409,
            )
        return (
            "alert",
            str(row.id),
            {
                "status": row.status,
                "notification_type": row.notification_type,
                "severity": row.severity,
            },
        )
    if definition.target_type == "lan_asset":
        selected = target_id or parameters.get("asset_id")
        try:
            asset_id = uuid.UUID(str(selected))
        except (ValueError, TypeError) as exc:
            raise ActionGatewayError(
                "invalid_target", "A valid existing LAN asset is required.", 422
            ) from exc
        asset = await db.get(LanAsset, asset_id)
        if asset is None:
            raise ActionGatewayError(
                "target_not_found", "The LAN asset does not exist.", 404
            )
        if action == "raventech.lan.asset.authorize" and asset.is_authorized:
            raise ActionGatewayError(
                "no_action_needed", "The LAN asset is already authorized.", 409
            )
        if (
            action in {"raventech.lan.asset.reject", "raventech.lan.asset.needs_review"}
            and not asset.is_authorized
        ):
            raise ActionGatewayError(
                "no_action_needed", "The LAN asset is already unauthorized.", 409
            )
        if (
            action == "raventech.lan.asset.reject"
            and asset.source == "host_neighbor_table"
        ):
            raise ActionGatewayError(
                "decision_not_representable",
                "This source can only be returned to review, not rejected.",
                409,
            )
        if (
            action == "raventech.lan.asset.needs_review"
            and asset.source != "host_neighbor_table"
        ):
            raise ActionGatewayError(
                "decision_not_supported",
                "This asset source has no distinct needs-review state.",
                409,
            )
        snapshot = {
            "is_authorized": asset.is_authorized,
            "monitoring_enabled": asset.monitoring_enabled,
            "ip_address": asset.ip_address,
            "mac_address": asset.mac_address,
            "source": asset.source,
        }
        return "lan_asset", str(asset.id), snapshot
    if action == "raventech.lan.discovery.run":
        if not settings.LAN_MONITORING_ENABLED:
            raise ActionGatewayError(
                "feature_disabled", "LAN discovery is disabled by configuration.", 403
            )
        from app.services.lan_monitoring import configured_networks

        networks = [str(item) for item in configured_networks()]
        return (
            "configured_lan",
            None,
            {"configured_private_cidrs": networks, "enabled": True},
        )
    if action == "raventech.job.retry":
        job_id = uuid.UUID(parameters["job_id"])
        job_target = (
            await db.execute(
                select(BackgroundJob).where(BackgroundJob.id == job_id)
            )
        ).scalar_one_or_none()
        if job_target is None or job_target.job_type not in _RETRYABLE_JOB_TYPES:
            raise ActionGatewayError(
                "target_not_found",
                "The job is not a registered safe retry target.",
                404,
            )
        if (
            job_target.status != "failed"
            or job_target.attempt_count >= job_target.max_attempts
        ):
            raise ActionGatewayError(
                "precondition_failed",
                "The job is not eligible for a bounded retry.",
                409,
            )
        return (
            "background_job",
            str(job_target.id),
            {
                "job_type": job_target.job_type,
                "status": job_target.status,
                "attempt_count": job_target.attempt_count,
                "max_attempts": job_target.max_attempts,
            },
        )
    asset_id = uuid.UUID(parameters["asset_id"])
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise ActionGatewayError(
            "target_not_found", "The LAN asset does not exist.", 404
        )
    if action == "raventech.lan.services.refresh" and not asset.is_authorized:
        raise ActionGatewayError(
            "protected_target",
            "Service observations require an authorized LAN asset.",
            403,
        )
    return (
        "lan_asset",
        str(asset.id),
        {
            "is_authorized": asset.is_authorized,
            "monitoring_enabled": asset.monitoring_enabled,
            "ip_address": asset.ip_address,
        },
    )


async def _policy_enabled(db: AsyncSession) -> bool:
    row = await db.get(ActionGatewayPolicy, 1)
    return row.enabled if row is not None else True


async def set_gateway_enabled(
    db: AsyncSession, user: User, enabled: bool
) -> ActionGatewayPolicy:
    row = await db.get(ActionGatewayPolicy, 1)
    if row is None:
        row = ActionGatewayPolicy(id=1, enabled=enabled, updated_by_user_id=user.id)
        db.add(row)
    else:
        row.enabled = enabled
        row.updated_by_user_id = user.id
        row.updated_at = datetime.now(UTC)
    if not enabled:
        pending = (
            (
                await db.execute(
                    select(ActionProposal)
                    .where(ActionProposal.status.in_(("awaiting_approval", "approved")))
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for proposal in pending:
            proposal.status = "cancelled"
            proposal.safe_error_code = "gateway_disabled"
            proposal.result_summary = (
                "Action Gateway was disabled; create a new proposal after it "
                "is enabled."
            )
            proposal.completed_at = now
            approval = (
                await db.execute(
                    select(ActionApproval)
                    .where(ActionApproval.proposal_id == proposal.id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if approval is not None:
                approval.consumed_at = now
    db.add(
        AuditLog(
            user_id=user.id,
            actor_id=user.id,
            action="action_gateway.policy_updated",
            resource_type="action_gateway_policy",
            details={"enabled": enabled},
            event_metadata={"enabled": enabled},
        )
    )
    await db.flush()
    return row


async def create_proposal(
    db: AsyncSession, user: User, body: ActionProposalCreate
) -> ActionProposal:
    definition = ACTION_REGISTRY.get(body.action_id)
    if definition is None:
        raise ActionGatewayError(
            "unsupported_action",
            "This action is not in the fixed RavenTech registry.",
            422,
        )
    _check_role(user, definition)
    if not await _policy_enabled(db):
        raise ActionGatewayError(
            "gateway_disabled",
            "The Action Gateway is disabled by an administrator.",
            403,
        )
    reason = _check_text(body.reason, limit=500)
    parameters = _parameters(definition, body.parameters)
    target_type, target_id, snapshot = await _database_target(
        db, user, definition, body.target_id, parameters, body.target_snapshot
    )
    if definition.target_type == "local_service":
        display = f"{snapshot['display_name']} ({snapshot['name']})"
    elif definition.target_type == "local_process":
        display = f"{snapshot['name']} ({snapshot['pid']})"
    elif target_id:
        display = (
            body.target_display_name
            or f"{definition.target_type.replace('_', ' ').title()} {target_id[:12]}"
        )
        display = _check_text(display, limit=180)
    else:
        display = "Configured authorized private LAN"
    if (
        body.target_display_name
        and definition.target_type.startswith("local_")
        and body.target_display_name.strip() != display
    ):
        raise ActionGatewayError(
            "invalid_target",
            "Display name does not match the current local inventory.",
            422,
        )
    evidence = [_check_text(item, limit=100) for item in body.supporting_evidence_ids]
    now = datetime.now(UTC)
    preconditions: dict[str, Any] = {
        "required_role": definition.required_role,
        "scope": "local_only",
        "target_snapshot_sha256": canonical_hash(snapshot),
    }
    proposal = ActionProposal(
        action_id=definition.action_id,
        requested_by_user_id=user.id,
        origin=body.origin,
        scope_type="local",
        scope_id=None,
        target_type=target_type,
        target_id=target_id,
        target_display_name=display,
        parameters=parameters,
        reason=reason,
        supporting_evidence_ids=evidence,
        risk_level=definition.risk_level,
        expected_effect=definition.expected_effect,
        possible_impact=definition.possible_impact,
        rollback_guidance=definition.rollback_guidance,
        preconditions=preconditions,
        target_snapshot=snapshot,
        proposal_hash="",
        status="awaiting_approval",
        expires_at=now + PROPOSAL_TTL,
    )
    hash_value = proposal_content_hash(proposal)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(60704, hashtext(:actor))"),
        {"actor": str(user.id)},
    )
    active_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ActionProposal)
                .where(
                    ActionProposal.requested_by_user_id == user.id,
                    ActionProposal.status.in_(
                        ("awaiting_approval", "approved", "executing")
                    ),
                    ActionProposal.expires_at > now,
                )
            )
        ).scalar_one()
    )
    if active_count >= MAX_ACTIVE_PER_USER:
        raise ActionGatewayError(
            "proposal_limit",
            "Too many pending actions; resolve an existing proposal first.",
            429,
        )
    duplicate = (
        await db.execute(
            select(ActionProposal)
            .where(
                ActionProposal.requested_by_user_id == user.id,
                ActionProposal.proposal_hash == hash_value,
                ActionProposal.created_at >= now - timedelta(seconds=30),
                ActionProposal.status.in_(("awaiting_approval", "approved")),
            )
            .order_by(ActionProposal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        return duplicate
    proposal.proposal_hash = hash_value
    db.add(proposal)
    await db.flush()
    _audit(
        db,
        user.id,
        "action_gateway.proposal_created",
        proposal,
        {"origin": body.origin, "risk_level": definition.risk_level},
    )
    return proposal


async def approve_proposal(
    db: AsyncSession,
    user: User,
    proposal_id: uuid.UUID,
    confirmation_text: str | None,
    current_snapshot: dict[str, Any] | None = None,
) -> tuple[ActionProposal, ActionApproval]:
    proposal = (
        await db.execute(
            select(ActionProposal)
            .where(ActionProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise ActionGatewayError(
            "proposal_not_found", "Action proposal was not found.", 404
        )
    definition = ACTION_REGISTRY.get(proposal.action_id)
    if definition is None:
        raise ActionGatewayError(
            "unsupported_action", "The action is no longer registered.", 409
        )
    _check_role(user, definition)
    if not await _policy_enabled(db):
        raise ActionGatewayError(
            "gateway_disabled",
            "The Action Gateway is disabled by an administrator.",
            403,
        )
    now = datetime.now(UTC)
    if proposal.status != "awaiting_approval":
        raise ActionGatewayError(
            "proposal_not_pending", "This proposal is no longer awaiting approval.", 409
        )
    if proposal.expires_at <= now:
        proposal.status = "expired"
        proposal.completed_at = now
        await db.flush()
        raise ActionGatewayError(
            "proposal_expired", "The proposal expired; create a fresh proposal.", 409
        )
    if proposal_content_hash(proposal) != proposal.proposal_hash:
        raise ActionGatewayError(
            "proposal_hash_mismatch", "Proposal integrity check failed.", 409
        )
    approval_snapshot = proposal.target_snapshot
    if definition.executor == "backend_fixed":
        _, current_target_id, current_snapshot = await _database_target(
            db, user, definition, proposal.target_id, proposal.parameters, {}
        )
        if current_target_id != proposal.target_id or canonical_hash(
            current_snapshot
        ) != canonical_hash(proposal.target_snapshot):
            raise ActionGatewayError(
                "state_changed_since_proposal",
                "Target state changed; create a fresh proposal.",
                409,
            )
    else:
        if current_snapshot is None:
            raise ActionGatewayError(
                "current_snapshot_required",
                "Refresh the local inventory before approving this action.",
                409,
            )
        try:
            approval_snapshot = _local_snapshot(definition, current_snapshot)
        except ActionGatewayError as exc:
            if exc.code == "precondition_failed":
                raise ActionGatewayError(
                    "state_changed_since_proposal",
                    "Local target state changed; create a fresh proposal.",
                    409,
                ) from exc
            raise
        if canonical_hash(approval_snapshot) != canonical_hash(
            proposal.target_snapshot
        ):
            raise ActionGatewayError(
                "state_changed_since_proposal",
                "Local target state changed; create a fresh proposal.",
                409,
            )
    phrase = approval_phrase(proposal.action_id, proposal.target_display_name)
    if definition.risk_level == "high" and confirmation_text != phrase:
        raise ActionGatewayError(
            "confirmation_mismatch",
            "Type the exact action confirmation shown in the review dialog.",
            422,
        )
    approval = ActionApproval(
        proposal_id=proposal.id,
        approved_by_user_id=user.id,
        approval_method="human_ui",
        confirmation_text=phrase
        if definition.risk_level == "high"
        else "approved_in_authenticated_ui",
        proposal_hash=proposal.proposal_hash,
        target_snapshot_hash=canonical_hash(approval_snapshot),
        expires_at=now + APPROVAL_TTL,
    )
    db.add(approval)
    proposal.status = "approved"
    await db.flush()
    _audit(
        db,
        user.id,
        "action_gateway.approved",
        proposal,
        {"risk_level": proposal.risk_level, "approval_method": "human_ui"},
    )
    return proposal, approval


async def reject_proposal(
    db: AsyncSession, user: User, proposal_id: uuid.UUID
) -> ActionProposal:
    proposal = (
        await db.execute(
            select(ActionProposal)
            .where(ActionProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise ActionGatewayError(
            "proposal_not_found", "Action proposal was not found.", 404
        )
    definition = ACTION_REGISTRY.get(proposal.action_id)
    if definition is None:
        raise ActionGatewayError(
            "unsupported_action", "The action is no longer registered.", 409
        )
    _check_role(user, definition)
    if proposal.status != "awaiting_approval":
        raise ActionGatewayError(
            "proposal_not_pending", "Only a pending proposal can be rejected.", 409
        )
    proposal.status = "rejected"
    proposal.completed_at = datetime.now(UTC)
    _audit(db, user.id, "action_gateway.rejected", proposal, {})
    return proposal


async def claim_local_execution(
    db: AsyncSession,
    user: User,
    proposal_id: uuid.UUID,
    current_snapshot: dict[str, Any],
) -> tuple[ActionProposal, ActionApproval]:
    proposal = (
        await db.execute(
            select(ActionProposal)
            .where(ActionProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise ActionGatewayError(
            "proposal_not_found", "Action proposal was not found.", 404
        )
    definition = ACTION_REGISTRY.get(proposal.action_id)
    if definition is None or definition.executor != "desktop_native":
        raise ActionGatewayError(
            "unsupported_action",
            "This action cannot be executed by the local desktop provider.",
            403,
        )
    _check_role(user, definition)
    if not await _policy_enabled(db):
        raise ActionGatewayError(
            "gateway_disabled",
            "The Action Gateway is disabled by an administrator.",
            403,
        )
    approval = (
        await db.execute(
            select(ActionApproval)
            .where(ActionApproval.proposal_id == proposal.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        proposal.status != "approved"
        or approval is None
        or approval.consumed_at is not None
    ):
        raise ActionGatewayError(
            "approval_unavailable", "A fresh unused human approval is required.", 409
        )
    if proposal.expires_at <= now or approval.expires_at <= now:
        proposal.status = "expired"
        proposal.completed_at = now
        approval.consumed_at = now
        raise ActionGatewayError(
            "approval_expired",
            "Approval expired; create and review a new proposal.",
            409,
        )
    if proposal_content_hash(proposal) != proposal.proposal_hash:
        raise ActionGatewayError(
            "proposal_hash_mismatch", "Proposal changed after approval.", 409
        )
    normalized = _local_snapshot(definition, current_snapshot)
    if canonical_hash(normalized) != canonical_hash(proposal.target_snapshot):
        raise ActionGatewayError(
            "state_changed_since_approval",
            "Local target identity or state changed after approval.",
            409,
        )
    if (
        approval.proposal_hash != proposal.proposal_hash
        or approval.target_snapshot_hash != canonical_hash(proposal.target_snapshot)
    ):
        raise ActionGatewayError(
            "approval_binding_invalid",
            "Approval does not match this proposal and target.",
            409,
        )
    await _acquire_native_target_lock(db, proposal, now)
    proposal.status = "executing"
    approval.consumed_at = now
    await db.flush()
    _audit(
        db,
        user.id,
        "action_gateway.execution_started",
        proposal,
        {"executor": "desktop_native"},
    )
    return proposal, approval


async def complete_local_execution(
    db: AsyncSession,
    user: User,
    proposal_id: uuid.UUID,
    *,
    success: bool,
    observed_state: str,
    safe_error_code: str | None,
) -> ActionProposal:
    proposal = (
        await db.execute(
            select(ActionProposal)
            .where(ActionProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise ActionGatewayError(
            "proposal_not_found", "Action proposal was not found.", 404
        )
    definition = ACTION_REGISTRY.get(proposal.action_id)
    if definition is None or definition.executor != "desktop_native":
        raise ActionGatewayError(
            "unsupported_action",
            "This local result does not match a registered action.",
            403,
        )
    _check_role(user, definition)
    if proposal.status != "executing":
        raise ActionGatewayError(
            "execution_not_claimed", "The one-use execution claim is unavailable.", 409
        )
    expected = (
        "terminated"
        if proposal.action_id == "raventech.process.terminate"
        else {"start": "running", "stop": "stopped", "restart": "running"}[
            proposal.action_id.rsplit(".", 1)[-1]
        ]
    )
    verified = success and observed_state == expected
    now = datetime.now(UTC)
    proposal.completed_at = now
    if verified:
        proposal.status = "completed"
        proposal.result_summary = f"Verified local state: {expected}."
        proposal.safe_error_code = None
    elif success:
        proposal.status = "verification_failed"
        proposal.result_summary = (
            "The local action returned, but its expected postcondition was "
            "not verified."
        )
        proposal.safe_error_code = "postcondition_not_verified"
    else:
        proposal.status = "failed"
        proposal.result_summary = (
            "The local provider refused or could not complete the action. "
            "Refresh local inventory and review the safe error."
        )
        proposal.safe_error_code = _safe_code(safe_error_code)
    _audit(
        db,
        user.id,
        "action_gateway.completed" if verified else "action_gateway.failed",
        proposal,
        {"verified": verified, "safe_error_code": proposal.safe_error_code},
    )
    if verified:
        db.add(
            MonitoringChangeEvent(
                event_type="action_gateway_completed",
                severity="high" if definition.risk_level == "high" else "info",
                title=f"{definition.display_name}: {proposal.target_display_name}"[
                    :255
                ],
                description=(
                    "Human-approved local action completed and its postcondition "
                    f"was verified. {proposal.result_summary}"
                )[:1000],
                source="action_gateway",
                old_value=str(proposal.target_snapshot.get("state", "running"))[:255],
                new_value=expected,
                event_metadata={
                    "action_id": proposal.action_id,
                    "proposal_id": str(proposal.id),
                    "approved_by_user_id": str(
                        (
                            await db.execute(
                                select(ActionApproval.approved_by_user_id).where(
                                    ActionApproval.proposal_id == proposal.id
                                )
                            )
                        ).scalar_one_or_none()
                    ),
                },
            )
        )
    await _release_native_target_lock(db, proposal)
    await db.flush()
    return proposal


async def execute_backend_action(
    db: AsyncSession, user: User, proposal_id: uuid.UUID
) -> ActionProposal:
    proposal = (
        await db.execute(
            select(ActionProposal)
            .where(ActionProposal.id == proposal_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise ActionGatewayError(
            "proposal_not_found", "Action proposal was not found.", 404
        )
    definition = ACTION_REGISTRY.get(proposal.action_id)
    if definition is None or definition.executor != "backend_fixed":
        raise ActionGatewayError(
            "desktop_executor_required",
            "This fixed local host action must be completed by the RavenTech "
            "desktop provider.",
            409,
        )
    _check_role(user, definition)
    if not await _policy_enabled(db):
        raise ActionGatewayError(
            "gateway_disabled",
            "The Action Gateway is disabled by an administrator.",
            403,
        )
    approval = (
        await db.execute(
            select(ActionApproval)
            .where(ActionApproval.proposal_id == proposal.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        proposal.status != "approved"
        or approval is None
        or approval.consumed_at is not None
    ):
        raise ActionGatewayError(
            "approval_unavailable", "A fresh unused human approval is required.", 409
        )
    if proposal.expires_at <= now or approval.expires_at <= now:
        proposal.status = "expired"
        proposal.completed_at = now
        approval.consumed_at = now
        raise ActionGatewayError(
            "approval_expired",
            "Approval expired; create and review a new proposal.",
            409,
        )
    if proposal_content_hash(proposal) != proposal.proposal_hash:
        raise ActionGatewayError(
            "proposal_hash_mismatch", "Proposal changed after approval.", 409
        )
    await db.execute(
        text("SELECT pg_advisory_xact_lock(60705, hashtext(:target))"),
        {"target": _target_lock_key(proposal)},
    )
    _, target_id, snapshot = await _database_target(
        db, user, definition, proposal.target_id, proposal.parameters, {}
    )
    if target_id != proposal.target_id or canonical_hash(snapshot) != canonical_hash(
        proposal.target_snapshot
    ):
        raise ActionGatewayError(
            "state_changed_since_approval", "Target state changed after approval.", 409
        )
    if (
        approval.proposal_hash != proposal.proposal_hash
        or approval.target_snapshot_hash != canonical_hash(proposal.target_snapshot)
    ):
        raise ActionGatewayError(
            "approval_binding_invalid",
            "Approval does not match this proposal and target.",
            409,
        )
    proposal.status = "executing"
    approval.consumed_at = now
    await db.flush()
    _audit(
        db,
        user.id,
        "action_gateway.execution_started",
        proposal,
        {"executor": "backend_fixed"},
    )

    result_summary = ""
    if proposal.action_id == "raventech.alert.acknowledge":
        from app.services.notification import mark_notification_read

        await mark_notification_read(db, user, uuid.UUID(proposal.target_id or ""))
        row = await db.get(Notification, uuid.UUID(proposal.target_id or ""))
        verified = row is not None and row.status == "read"
        result_summary = (
            "Alert acknowledgement verified."
            if verified
            else "Alert acknowledgement was not verified."
        )
    elif proposal.action_id.startswith("raventech.lan.asset."):
        asset_id = uuid.UUID(proposal.target_id or "")
        asset = await db.get(LanAsset, asset_id)
        if asset is None:
            raise ActionGatewayError(
                "target_not_found", "The LAN asset no longer exists.", 404
            )
        if proposal.action_id.endswith("authorize"):
            patch = LanAssetUpdate(is_authorized=True, monitoring_enabled=True)
        elif proposal.action_id.endswith("reject"):
            patch = LanAssetUpdate(is_authorized=False, monitoring_enabled=False)
        else:
            patch = LanAssetUpdate(is_authorized=False)
        from app.services.lan_monitoring import update_lan_asset

        await update_lan_asset(db, user, asset_id, patch)
        await db.refresh(asset)
        from app.services.lan_monitoring import _trust_state

        if proposal.action_id.endswith("needs_review"):
            verified = _trust_state(asset) == "needs_review"
        elif proposal.action_id.endswith("reject"):
            verified = (
                _trust_state(asset) == "unauthorized" and not asset.monitoring_enabled
            )
        else:
            verified = _trust_state(asset) in {"authorized", "known_agent"}
        result_summary = (
            "LAN asset decision verified."
            if verified
            else "LAN asset decision was not verified."
        )
    elif proposal.action_id == "raventech.lan.discovery.run":
        from app.services.background_jobs import enqueue_job

        job = await enqueue_job(
            db,
            "monitoring.lan_discovery",
            {},
            priority=20,
            dedupe_key=f"action-discovery:{proposal.id}",
            requested_by_user_id=user.id,
        )
        verified = job.job_type == "monitoring.lan_discovery" and job.status in {
            "queued",
            "scheduled",
            "running",
            "completed",
        }
        result_summary = f"Bounded LAN discovery job queued ({job.id})."
    elif proposal.action_id == "raventech.lan.services.refresh":
        from app.services.background_jobs import enqueue_job

        asset_id = uuid.UUID(proposal.parameters["asset_id"])
        job = await enqueue_job(
            db,
            "monitoring.service_observation.asset",
            {"asset_id": str(asset_id)},
            priority=20,
            dedupe_key=f"action-service-refresh:{proposal.id}",
            requested_by_user_id=user.id,
        )
        verified = (
            job.job_type == "monitoring.service_observation.asset"
            and job.asset_id == asset_id
            and job.status in {
                "queued",
                "scheduled",
                "running",
                "completed",
            }
        )
        result_summary = f"Bounded service observation job queued ({job.id})."
    elif proposal.action_id == "raventech.posture.recompute":
        from app.services.background_jobs import enqueue_job

        asset_id = uuid.UUID(proposal.parameters["asset_id"])
        job = await enqueue_job(
            db,
            "posture.recompute",
            {"asset_id": str(asset_id)},
            priority=50,
            dedupe_key=f"action-posture:{proposal.id}",
            requested_by_user_id=user.id,
        )
        verified = job.asset_id == asset_id and job.status in {
            "queued",
            "scheduled",
            "running",
            "completed",
        }
        result_summary = f"Posture recomputation job queued ({job.id})."
    elif proposal.action_id == "raventech.job.retry":
        job_id = uuid.UUID(proposal.parameters["job_id"])
        retry_job = (
            await db.execute(
                select(BackgroundJob)
                .where(BackgroundJob.id == job_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if (
            retry_job is None
            or retry_job.job_type not in _RETRYABLE_JOB_TYPES
            or retry_job.status != "failed"
            or retry_job.attempt_count >= retry_job.max_attempts
        ):
            raise ActionGatewayError(
                "state_changed_since_approval",
                "The safe job retry preconditions changed.",
                409,
            )
        retry_job.status = "queued"
        retry_job.scheduled_at = now
        retry_job.next_retry_at = None
        db.add(
            BackgroundJobEvent(
                job_id=retry_job.id,
                event_type="retry_scheduled",
                detail="Operator queued an approved bounded retry.",
            )
        )
        verified = retry_job.status == "queued"
        result_summary = f"Allowlisted job retry queued ({retry_job.id})."
    else:
        raise ActionGatewayError(
            "unsupported_action", "The action has no fixed application executor.", 403
        )

    proposal.completed_at = datetime.now(UTC)
    proposal.status = "completed" if verified else "verification_failed"
    proposal.result_summary = result_summary[:500]
    proposal.safe_error_code = None if verified else "postcondition_not_verified"
    _audit(
        db,
        user.id,
        "action_gateway.completed" if verified else "action_gateway.failed",
        proposal,
        {"verified": verified},
    )
    db.add(
        MonitoringChangeEvent(
            asset_id=uuid.UUID(proposal.target_id)
            if proposal.target_type == "lan_asset" and proposal.target_id
            else None,
            event_type="action_gateway_completed"
            if verified
            else "action_gateway_verification_failed",
            severity="high" if definition.risk_level == "high" else "info",
            title=f"{definition.display_name}: {proposal.target_display_name}"[:255],
            description=(result_summary or "Action result unavailable.")[:1000],
            source="action_gateway",
            event_metadata={
                "action_id": proposal.action_id,
                "proposal_id": str(proposal.id),
                "approved_by_user_id": str(user.id),
            },
        )
    )
    await db.flush()
    return proposal


async def list_proposals(
    db: AsyncSession, user: User, *, status: str | None = None, limit: int = 100
) -> list[ActionProposal]:
    query = select(ActionProposal)
    if user.role != "admin":
        query = query.where(ActionProposal.requested_by_user_id == user.id)
    if status:
        query = query.where(ActionProposal.status == status)
    rows = await db.execute(
        query.order_by(ActionProposal.created_at.desc()).limit(limit)
    )
    return list(rows.scalars().all())


async def proposal_view(db: AsyncSession, proposal: ActionProposal) -> dict[str, Any]:
    approval = (
        await db.execute(
            select(ActionApproval).where(ActionApproval.proposal_id == proposal.id)
        )
    ).scalar_one_or_none()
    return {
        "id": proposal.id,
        "action_id": proposal.action_id,
        "requested_by_user_id": proposal.requested_by_user_id,
        "approved_by_user_id": approval.approved_by_user_id if approval else None,
        "origin": proposal.origin,
        "scope_type": proposal.scope_type,
        "scope_id": proposal.scope_id,
        "target_type": proposal.target_type,
        "target_id": proposal.target_id,
        "target_display_name": proposal.target_display_name,
        "target_snapshot": proposal.target_snapshot,
        "preconditions": proposal.preconditions,
        "parameters": proposal.parameters,
        "reason": proposal.reason,
        "supporting_evidence_ids": proposal.supporting_evidence_ids,
        "risk_level": proposal.risk_level,
        "expected_effect": proposal.expected_effect,
        "possible_impact": proposal.possible_impact,
        "rollback_guidance": proposal.rollback_guidance,
        "status": "expired"
        if proposal.status in {"awaiting_approval", "approved"}
        and proposal.expires_at <= datetime.now(UTC)
        else proposal.status,
        "expires_at": proposal.expires_at,
        "created_at": proposal.created_at,
        "completed_at": proposal.completed_at,
        "proposal_hash": proposal.proposal_hash,
        "approval_expires_at": approval.expires_at if approval else None,
        "result_summary": proposal.result_summary,
        "safe_error_code": proposal.safe_error_code,
        "approval_confirmation": approval_phrase(
            proposal.action_id, proposal.target_display_name
        ),
    }


def _safe_code(value: str | None) -> str:
    allowed = {
        "permission_denied",
        "protected_target",
        "already_exited",
        "identity_changed",
        "provider_unavailable",
        "timeout",
        "action_failed",
    }
    return value if value in allowed else "action_failed"


def _audit(
    db: AsyncSession,
    actor_id: uuid.UUID,
    action: str,
    proposal: ActionProposal,
    metadata: dict[str, Any],
) -> None:
    safe = {
        "proposal_id": str(proposal.id),
        "action_id": proposal.action_id,
        "target_type": proposal.target_type,
        "target_id": proposal.target_id,
        **metadata,
    }
    db.add(
        AuditLog(
            user_id=actor_id,
            actor_id=actor_id,
            action=action,
            resource_type="action_proposal",
            resource_id=proposal.id,
            details=safe,
            event_metadata=safe,
        )
    )
