from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.lan_monitoring import (
    LanAgentRegistration,
    LanAgentRegistrationResponse,
    LanAgentTelemetryIngest,
    LanAgentTelemetryResponse,
    LanAssetListResponse,
    LanAssetResponse,
    LanAssetCriticalityUpdate,
    LanAssetUpdate,
    LanDiscoveryRequest,
    LanDiscoveryResponse,
    LanOpenPortsResponse,
    LanServiceCheckResponse,
    LanServiceListResponse,
    LanTelemetryListResponse,
    MonitoringActivationStatus,
    TargetServiceCheckStatus,
)
from app.schemas.agent_management import (
    AgentInventoryItem,
    AgentInventoryResponse,
    AgentUpdate,
    AssetGroupCreate,
    AssetGroupListResponse,
    AssetGroupResponse,
    AssetGroupUpdate,
    EnrollmentTokenCreate,
    EnrollmentTokenCreated,
    EnrollmentTokenListResponse,
    EnrollmentTokenResponse,
    ServiceBaselineCreate,
    ServiceBaselineListResponse,
    ServiceBaselineResponse,
    ServiceBaselineUpdate,
)
from app.schemas.endpoint_posture import (
    EndpointPostureOverviewResponse,
    EndpointRecommendationAction,
    EndpointRecommendationListResponse,
    EndpointRecommendationResponse,
    EndpointRecommendationUpdate,
    EndpointSecurityPostureResponse,
    RecommendationSeverity,
    RecommendationStatus,
)
from app.schemas.vulnerability_baseline import (
    VulnerabilityBaselineFindingResponse,
    VulnerabilityBaselineListResponse,
    VulnerabilityBaselineOverviewResponse,
    VulnerabilityBaselineRunResponse,
    VulnerabilityBaselineUpdate,
)
from app.schemas.monitoring import (
    AgentTelemetryIngest,
    AgentTelemetryIngestResponse,
    MonitoringAlertsResponse,
    MonitoringAssetsResponse,
    MonitoringOverviewResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.schemas.monitoring_policy import (
    AlertSuppressionCreate,
    AlertSuppressionResponse,
    MaintenanceWindowCreate,
    MaintenanceWindowListResponse,
    MaintenanceWindowResponse,
    MaintenanceWindowUpdate,
    MonitoringPolicyCreate,
    MonitoringPolicyListResponse,
    MonitoringPolicyResponse,
    MonitoringPolicyUpdate,
)
from app.schemas.monitoring_history import (
    AssetHistoryResponse,
    ChangeSeverity,
    MonitoringChangeAcknowledgeResponse,
    MonitoringChangeListResponse,
    MonitoringChangeOverviewResponse,
    ServiceHistoryListResponse,
)
from app.schemas.monitoring_triage import (
    MonitoringTriageAssign,
    MonitoringTriageItem,
    MonitoringTriageListResponse,
    MonitoringTriageMute,
    MonitoringTriageResolution,
    MonitoringTriageUpdate,
    TriageSeverity,
    TriageStatus,
)
from app.services.monitoring_policy import (
    AlertNotFoundError,
    AlertSuppressionConflictError,
    MaintenanceWindowNotFoundError,
    MonitoringPolicyNotFoundError,
    create_policy,
    create_window,
    list_policies,
    list_windows,
    suppression_response,
    suppress_alert,
    unsuppress_alert,
    update_policy,
    update_window,
    window_response,
)
from app.services.agent_management import (
    AgentCredentialError,
    AgentManagementConflictError,
    AgentManagementNotFoundError,
    create_baseline,
    create_enrollment_token,
    create_group,
    delete_baseline,
    delete_group,
    get_agent,
    list_agents,
    list_baselines,
    list_enrollment_tokens,
    list_groups,
    revoke_enrollment_token,
    rotate_enrollment_token,
    update_agent,
    update_baseline,
    update_group,
    validate_agent_credential,
)
from app.services.endpoint_posture import (
    EndpointPostureNotFoundError,
    EndpointRecommendationConflictError,
    EndpointRecommendationNotFoundError,
    acknowledge_recommendation,
    assess_asset_posture,
    get_asset_posture,
    get_posture_overview,
    list_recommendations,
    resolve_recommendation,
    update_recommendation,
)
from app.services.monitoring_history import (
    ChangeAcknowledgement,
    MonitoringChangeAlreadyAcknowledgedError,
    MonitoringChangeNotFoundError,
    MonitoringHistoryAssetNotFoundError,
    acknowledge_change,
    asset_history,
    changes_overview,
    list_changes,
    service_history,
)
from app.services.monitoring_triage import (
    MonitoringTriageConflictError,
    MonitoringTriageNotFoundError,
    MonitoringTriageOwnerNotFoundError,
    MonitoringTriageValidationError,
    assign_triage,
    false_positive_triage,
    list_triage,
    mute_triage,
    resolve_triage,
    update_triage,
)
from app.services.investigation import InvestigationNotFoundError
from app.services.target import TargetNotFoundError, get_target
from app.services.local_monitoring import (
    get_asset_watch,
    get_monitoring_alerts,
    get_monitoring_overview,
    get_service_status,
    get_system_metrics,
    ingest_agent_telemetry,
)
from app.services.lan_monitoring import (
    LanAssetNotFoundError,
    LanConfigurationError,
    LanDiscoveryRateLimitedError,
    LanMonitoringDisabledError,
    LanServiceCheckDisabledError,
    check_asset_services,
    check_target_services,
    discover_lan,
    get_lan_asset,
    get_monitoring_activation,
    get_target_service_check_status,
    ingest_agent_telemetry as ingest_lan_agent_telemetry,
    list_asset_services,
    list_asset_telemetry,
    list_lan_assets,
    list_open_ports,
    notify_discovery_failure,
    register_agent,
    update_lan_asset,
)
from app.services.vulnerability_baseline import (
    VulnerabilityBaselineDisabledError,
    VulnerabilityBaselineFindingNotFoundError,
    get_baseline_overview,
    list_baseline_findings,
    run_vulnerability_baseline,
    update_asset_criticality,
    update_baseline_finding,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/posture/overview", response_model=EndpointPostureOverviewResponse)
async def endpoint_posture_overview(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointPostureOverviewResponse:
    return await _safe_posture_call(get_posture_overview, db, current_user)


@router.get(
    "/lan/assets/{asset_id}/posture",
    response_model=EndpointSecurityPostureResponse,
)
async def endpoint_asset_posture(
    asset_id: uuid.UUID,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointSecurityPostureResponse:
    return await _safe_posture_call(get_asset_posture, db, asset_id)


@router.post(
    "/lan/assets/{asset_id}/posture/assess",
    response_model=EndpointSecurityPostureResponse,
)
async def endpoint_asset_posture_assess(
    asset_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointSecurityPostureResponse:
    return await _safe_posture_call(assess_asset_posture, db, current_user, asset_id)


@router.get("/recommendations", response_model=EndpointRecommendationListResponse)
async def endpoint_recommendations(
    recommendation_status: RecommendationStatus | None = Query(
        default=None, alias="status"
    ),
    severity: RecommendationSeverity | None = None,
    asset_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointRecommendationListResponse:
    return await _safe_posture_call(
        list_recommendations,
        db,
        status=recommendation_status,
        severity=severity,
        asset_id=asset_id,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/recommendations/{recommendation_id}",
    response_model=EndpointRecommendationResponse,
)
async def endpoint_recommendation_update(
    recommendation_id: uuid.UUID,
    body: EndpointRecommendationUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointRecommendationResponse:
    return await _safe_posture_call(
        update_recommendation, db, current_user, recommendation_id, body
    )


@router.post(
    "/recommendations/{recommendation_id}/acknowledge",
    response_model=EndpointRecommendationResponse,
)
async def endpoint_recommendation_acknowledge(
    recommendation_id: uuid.UUID,
    body: EndpointRecommendationAction,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointRecommendationResponse:
    return await _safe_posture_call(
        acknowledge_recommendation, db, current_user, recommendation_id, body
    )


@router.post(
    "/recommendations/{recommendation_id}/resolve",
    response_model=EndpointRecommendationResponse,
)
async def endpoint_recommendation_resolve(
    recommendation_id: uuid.UUID,
    body: EndpointRecommendationAction,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EndpointRecommendationResponse:
    return await _safe_posture_call(
        resolve_recommendation, db, current_user, recommendation_id, body
    )


@router.get("/activation", response_model=MonitoringActivationStatus)
async def monitoring_activation_endpoint(
    _current_user: User = Depends(require_role("admin", "analyst")),
) -> MonitoringActivationStatus:
    return get_monitoring_activation()


@router.get("/triage", response_model=MonitoringTriageListResponse)
async def monitoring_triage_endpoint(
    triage_status: TriageStatus | None = Query(default=None, alias="status"),
    severity: TriageSeverity | None = None,
    source: str | None = Query(default=None, min_length=1, max_length=80),
    asset_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringTriageListResponse:
    return await _safe_triage_call(
        list_triage,
        db,
        current_user,
        status=triage_status,
        severity=severity,
        source=source,
        asset_id=asset_id,
        limit=limit,
        offset=offset,
    )


@router.patch("/triage/{alert_id}", response_model=MonitoringTriageItem)
async def monitoring_triage_update_endpoint(
    alert_id: uuid.UUID,
    body: MonitoringTriageUpdate,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringTriageItem:
    return await _safe_triage_call(update_triage, db, current_user, alert_id, body)


@router.post("/triage/{alert_id}/assign", response_model=MonitoringTriageItem)
async def monitoring_triage_assign_endpoint(
    alert_id: uuid.UUID,
    body: MonitoringTriageAssign,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringTriageItem:
    return await _safe_triage_call(assign_triage, db, current_user, alert_id, body)


@router.post("/triage/{alert_id}/resolve", response_model=MonitoringTriageItem)
async def monitoring_triage_resolve_endpoint(
    alert_id: uuid.UUID,
    body: MonitoringTriageResolution,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringTriageItem:
    return await _safe_triage_call(resolve_triage, db, current_user, alert_id, body)


@router.post("/triage/{alert_id}/false-positive", response_model=MonitoringTriageItem)
async def monitoring_triage_false_positive_endpoint(
    alert_id: uuid.UUID,
    body: MonitoringTriageResolution,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringTriageItem:
    return await _safe_triage_call(
        false_positive_triage, db, current_user, alert_id, body
    )


@router.post("/triage/{alert_id}/mute", response_model=MonitoringTriageItem)
async def monitoring_triage_mute_endpoint(
    alert_id: uuid.UUID,
    body: MonitoringTriageMute,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringTriageItem:
    return await _safe_triage_call(mute_triage, db, current_user, alert_id, body)


@router.get("/changes", response_model=MonitoringChangeListResponse)
async def monitoring_changes_endpoint(
    asset_id: uuid.UUID | None = None,
    event_type: str | None = Query(default=None, min_length=1, max_length=80),
    severity: ChangeSeverity | None = None,
    acknowledgement: ChangeAcknowledgement | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringChangeListResponse:
    if date_from and date_to:
        normalized_from = (
            date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        )
        normalized_to = date_to if date_to.tzinfo else date_to.replace(tzinfo=UTC)
        if normalized_from > normalized_to:
            raise HTTPException(
                status_code=422, detail="date_from must be before date_to"
            )
    return await _safe_history_call(
        list_changes,
        db,
        limit=limit,
        offset=offset,
        asset_id=asset_id,
        event_type=event_type,
        severity=severity,
        acknowledgement=acknowledgement,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/changes/overview", response_model=MonitoringChangeOverviewResponse)
async def monitoring_changes_overview_endpoint(
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringChangeOverviewResponse:
    return await _safe_history_call(changes_overview, db)


@router.patch(
    "/changes/{change_id}/acknowledge",
    response_model=MonitoringChangeAcknowledgeResponse,
)
async def monitoring_change_acknowledge_endpoint(
    change_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringChangeAcknowledgeResponse:
    return await _safe_history_call(acknowledge_change, db, current_user, change_id)


@router.get("/policies", response_model=MonitoringPolicyListResponse)
async def monitoring_policies_endpoint(
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringPolicyListResponse:
    items = await list_policies(db)
    return MonitoringPolicyListResponse(
        total=len(items),
        items=[MonitoringPolicyResponse.model_validate(item) for item in items],
    )


@router.post(
    "/policies",
    response_model=MonitoringPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def monitoring_policy_create_endpoint(
    body: MonitoringPolicyCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringPolicyResponse:
    try:
        return MonitoringPolicyResponse.model_validate(
            await create_policy(db, current_user, body)
        )
    except AlertSuppressionConflictError as exc:
        raise HTTPException(
            status_code=409, detail="A policy with that rule key already exists."
        ) from exc


@router.patch("/policies/{policy_id}", response_model=MonitoringPolicyResponse)
async def monitoring_policy_update_endpoint(
    policy_id: uuid.UUID,
    body: MonitoringPolicyUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> MonitoringPolicyResponse:
    try:
        return MonitoringPolicyResponse.model_validate(
            await update_policy(db, current_user, policy_id, body)
        )
    except MonitoringPolicyNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Monitoring policy not found."
        ) from exc


@router.get("/maintenance-windows", response_model=MaintenanceWindowListResponse)
async def maintenance_windows_endpoint(
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceWindowListResponse:
    items = await list_windows(db)
    return MaintenanceWindowListResponse(
        total=len(items), items=[window_response(item) for item in items]
    )


@router.post(
    "/maintenance-windows",
    response_model=MaintenanceWindowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def maintenance_window_create_endpoint(
    body: MaintenanceWindowCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceWindowResponse:
    return window_response(await create_window(db, current_user, body))


@router.patch(
    "/maintenance-windows/{window_id}", response_model=MaintenanceWindowResponse
)
async def maintenance_window_update_endpoint(
    window_id: uuid.UUID,
    body: MaintenanceWindowUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceWindowResponse:
    try:
        return window_response(await update_window(db, current_user, window_id, body))
    except MaintenanceWindowNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Maintenance window not found."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid maintenance window range."
        ) from exc


@router.post("/alerts/{alert_id}/suppress", response_model=AlertSuppressionResponse)
async def monitoring_alert_suppress_endpoint(
    alert_id: uuid.UUID,
    body: AlertSuppressionCreate,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> AlertSuppressionResponse:
    try:
        return suppression_response(
            await suppress_alert(db, current_user, alert_id, body)
        )
    except AlertNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Monitoring alert not found."
        ) from exc
    except AlertSuppressionConflictError as exc:
        raise HTTPException(
            status_code=409, detail="This alert is already suppressed."
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="Only an administrator can suppress a critical alert.",
        ) from exc


@router.post("/alerts/{alert_id}/unsuppress", response_model=AlertSuppressionResponse)
async def monitoring_alert_unsuppress_endpoint(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> AlertSuppressionResponse:
    try:
        return suppression_response(await unsuppress_alert(db, current_user, alert_id))
    except AlertNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Monitoring alert not found."
        ) from exc
    except AlertSuppressionConflictError as exc:
        raise HTTPException(
            status_code=409, detail="This alert has no active suppression."
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="You cannot change this alert suppression."
        ) from exc


@router.get("/agent-tokens", response_model=EnrollmentTokenListResponse)
async def agent_tokens_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentTokenListResponse:
    return await _safe_agent_management_call(list_enrollment_tokens, db)


@router.post(
    "/agent-tokens",
    response_model=EnrollmentTokenCreated,
    status_code=status.HTTP_201_CREATED,
)
async def agent_token_create_endpoint(
    body: EnrollmentTokenCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentTokenCreated:
    return await _safe_agent_management_call(
        create_enrollment_token, db, current_user, body
    )


@router.post("/agent-tokens/{token_id}/revoke", response_model=EnrollmentTokenResponse)
async def agent_token_revoke_endpoint(
    token_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentTokenResponse:
    return await _safe_agent_management_call(
        revoke_enrollment_token, db, current_user, token_id
    )


@router.post("/agent-tokens/{token_id}/rotate", response_model=EnrollmentTokenCreated)
async def agent_token_rotate_endpoint(
    token_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentTokenCreated:
    return await _safe_agent_management_call(
        rotate_enrollment_token, db, current_user, token_id
    )


@router.get("/agents", response_model=AgentInventoryResponse)
async def agents_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AgentInventoryResponse:
    return await _safe_agent_management_call(list_agents, db)


@router.get("/agents/{agent_id}", response_model=AgentInventoryItem)
async def agent_endpoint(
    agent_id: uuid.UUID,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AgentInventoryItem:
    return await _safe_agent_management_call(get_agent, db, agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentInventoryItem)
async def agent_update_endpoint(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AgentInventoryItem:
    return await _safe_agent_management_call(
        update_agent, db, current_user, agent_id, body
    )


@router.get("/asset-groups", response_model=AssetGroupListResponse)
async def asset_groups_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AssetGroupListResponse:
    return await _safe_agent_management_call(list_groups, db)


@router.post(
    "/asset-groups",
    response_model=AssetGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def asset_group_create_endpoint(
    body: AssetGroupCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AssetGroupResponse:
    return await _safe_agent_management_call(create_group, db, current_user, body)


@router.patch("/asset-groups/{group_id}", response_model=AssetGroupResponse)
async def asset_group_update_endpoint(
    group_id: uuid.UUID,
    body: AssetGroupUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AssetGroupResponse:
    return await _safe_agent_management_call(
        update_group, db, current_user, group_id, body
    )


@router.delete("/asset-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def asset_group_delete_endpoint(
    group_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _safe_agent_management_call(delete_group, db, current_user, group_id)


@router.get("/service-baselines", response_model=ServiceBaselineListResponse)
async def service_baselines_endpoint(
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> ServiceBaselineListResponse:
    return await _safe_agent_management_call(list_baselines, db)


@router.post(
    "/service-baselines",
    response_model=ServiceBaselineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def service_baseline_create_endpoint(
    body: ServiceBaselineCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ServiceBaselineResponse:
    return await _safe_agent_management_call(create_baseline, db, current_user, body)


@router.patch(
    "/service-baselines/{baseline_id}", response_model=ServiceBaselineResponse
)
async def service_baseline_update_endpoint(
    baseline_id: uuid.UUID,
    body: ServiceBaselineUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ServiceBaselineResponse:
    return await _safe_agent_management_call(
        update_baseline, db, current_user, baseline_id, body
    )


@router.delete(
    "/service-baselines/{baseline_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def service_baseline_delete_endpoint(
    baseline_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _safe_agent_management_call(delete_baseline, db, current_user, baseline_id)


@router.get("/overview", response_model=MonitoringOverviewResponse)
async def monitoring_overview_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonitoringOverviewResponse:
    try:
        return await get_monitoring_overview(db, request.app.state.redis, current_user)
    except Exception as exc:
        logger.exception("monitoring.overview failed")
        raise _monitoring_unavailable() from exc


@router.get("/services", response_model=MonitoringServicesResponse)
async def monitoring_services_endpoint(
    request: Request,
    _current_user: User = Depends(get_current_user),
) -> MonitoringServicesResponse:
    return await get_service_status(request.app.state.redis)


@router.get("/system", response_model=MonitoringSystemResponse)
async def monitoring_system_endpoint(
    _current_user: User = Depends(get_current_user),
) -> MonitoringSystemResponse:
    return get_system_metrics()


@router.get("/assets", response_model=MonitoringAssetsResponse)
async def monitoring_assets_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonitoringAssetsResponse:
    try:
        return await get_asset_watch(db, current_user)
    except Exception as exc:
        logger.exception("monitoring.assets failed")
        raise _monitoring_unavailable() from exc


@router.get("/alerts", response_model=MonitoringAlertsResponse)
async def monitoring_alerts_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonitoringAlertsResponse:
    try:
        services = await get_service_status(request.app.state.redis)
        system = get_system_metrics()
        assets = await get_asset_watch(db, current_user)
        return await get_monitoring_alerts(
            db,
            current_user,
            services=services,
            system=system,
            assets=assets,
        )
    except Exception as exc:
        logger.exception("monitoring.alerts failed")
        raise _monitoring_unavailable() from exc


@router.post(
    "/agent/ingest",
    response_model=AgentTelemetryIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def monitoring_agent_ingest_endpoint(
    body: AgentTelemetryIngest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AgentTelemetryIngestResponse:
    return await ingest_agent_telemetry(db, current_user, body)


@router.get("/lan/assets", response_model=LanAssetListResponse)
async def lan_assets_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetListResponse:
    return await _safe_lan_call(list_lan_assets, db)


@router.get("/lan/assets/{asset_id}", response_model=LanAssetResponse)
async def lan_asset_endpoint(
    asset_id: uuid.UUID,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetResponse:
    return await _safe_lan_call(get_lan_asset, db, asset_id)


@router.post("/lan/discover", response_model=LanDiscoveryResponse)
async def lan_discover_endpoint(
    body: LanDiscoveryRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanDiscoveryResponse:
    try:
        return await _safe_lan_call(discover_lan, db, current_user, body)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            await db.rollback()
            try:
                await notify_discovery_failure(db, current_user)
                await db.flush()
                await db.commit()
            except Exception:
                logger.exception("monitoring.lan failure notification skipped")
        raise


@router.patch("/lan/assets/{asset_id}", response_model=LanAssetResponse)
async def lan_asset_update_endpoint(
    asset_id: uuid.UUID,
    body: LanAssetUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetResponse:
    return await _safe_lan_call(update_lan_asset, db, current_user, asset_id, body)


@router.patch("/lan/assets/{asset_id}/criticality", response_model=LanAssetResponse)
async def lan_asset_criticality_endpoint(
    asset_id: uuid.UUID,
    body: LanAssetCriticalityUpdate,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetResponse:
    return await _safe_lan_call(
        update_asset_criticality, db, current_user, asset_id, body
    )


@router.get("/lan/assets/{asset_id}/telemetry", response_model=LanTelemetryListResponse)
async def lan_asset_telemetry_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanTelemetryListResponse:
    return await _safe_lan_call(list_asset_telemetry, db, asset_id, limit)


@router.get("/lan/assets/{asset_id}/services", response_model=LanServiceListResponse)
async def lan_asset_services_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanServiceListResponse:
    return await _safe_lan_call(list_asset_services, db, asset_id, limit)


@router.get("/lan/assets/{asset_id}/history", response_model=AssetHistoryResponse)
async def lan_asset_history_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AssetHistoryResponse:
    return await _safe_history_call(asset_history, db, asset_id, limit, offset)


@router.get(
    "/lan/assets/{asset_id}/service-history",
    response_model=ServiceHistoryListResponse,
)
async def lan_asset_service_history_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ServiceHistoryListResponse:
    return await _safe_history_call(service_history, db, asset_id, limit, offset)


@router.post(
    "/lan/assets/{asset_id}/service-check", response_model=LanServiceCheckResponse
)
async def lan_asset_service_check_endpoint(
    asset_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanServiceCheckResponse:
    return await _safe_lan_call(check_asset_services, db, current_user, asset_id)


@router.get(
    "/targets/{target_id}/service-check", response_model=TargetServiceCheckStatus
)
async def target_service_check_status_endpoint(
    target_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> TargetServiceCheckStatus:
    target = await _monitoring_target(db, current_user, target_id)
    return await _safe_lan_call(get_target_service_check_status, db, target)


@router.post(
    "/targets/{target_id}/service-check", response_model=LanServiceCheckResponse
)
async def target_service_check_endpoint(
    target_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanServiceCheckResponse:
    target = await _monitoring_target(db, current_user, target_id)
    return await _safe_lan_call(check_target_services, db, current_user, target)


@router.get("/services/open-ports", response_model=LanOpenPortsResponse)
async def monitoring_open_ports_endpoint(
    limit: int = Query(default=500, ge=1, le=500),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanOpenPortsResponse:
    return await _safe_lan_call(list_open_ports, db, limit)


@router.post(
    "/agent/register",
    response_model=LanAgentRegistrationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def lan_agent_register_endpoint(
    body: LanAgentRegistration,
    agent_token: str | None = Header(default=None, alias="X-LAN-Agent-Token"),
    db: AsyncSession = Depends(get_db),
) -> LanAgentRegistrationResponse:
    credential = await _safe_agent_credential(db, agent_token, body.ip_address)
    return await _safe_lan_call(register_agent, db, body, credential)


@router.post(
    "/agent/telemetry",
    response_model=LanAgentTelemetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def lan_agent_telemetry_ingest_endpoint(
    body: LanAgentTelemetryIngest,
    agent_token: str | None = Header(default=None, alias="X-LAN-Agent-Token"),
    db: AsyncSession = Depends(get_db),
) -> LanAgentTelemetryResponse:
    await _safe_agent_credential(db, agent_token, asset_id=body.asset_id)
    return await _safe_lan_call(ingest_lan_agent_telemetry, db, body)


@router.get("/vulnerabilities", response_model=VulnerabilityBaselineListResponse)
async def vulnerability_baseline_list_endpoint(
    finding_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(open|acknowledged|in_progress|resolved|false_positive)$",
    ),
    severity: str | None = Query(
        default=None, pattern="^(info|low|medium|high|critical)$"
    ),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> VulnerabilityBaselineListResponse:
    return await _safe_baseline_call(
        list_baseline_findings,
        db,
        current_user,
        status=finding_status,
        severity=severity,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/vulnerabilities/overview", response_model=VulnerabilityBaselineOverviewResponse
)
async def vulnerability_baseline_overview_endpoint(
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> VulnerabilityBaselineOverviewResponse:
    return await _safe_baseline_call(get_baseline_overview, db, current_user)


@router.post(
    "/vulnerabilities/run-baseline", response_model=VulnerabilityBaselineRunResponse
)
async def vulnerability_baseline_run_endpoint(
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> VulnerabilityBaselineRunResponse:
    return await _safe_baseline_call(run_vulnerability_baseline, db, current_user)


@router.patch(
    "/vulnerabilities/{finding_id}", response_model=VulnerabilityBaselineFindingResponse
)
async def vulnerability_baseline_update_endpoint(
    finding_id: uuid.UUID,
    body: VulnerabilityBaselineUpdate,
    current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> VulnerabilityBaselineFindingResponse:
    return await _safe_baseline_call(
        update_baseline_finding, db, current_user, finding_id, body
    )


def _monitoring_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Monitoring data is temporarily unavailable.",
    )


async def _monitoring_target(db: AsyncSession, user: User, target_id: uuid.UUID) -> Any:
    try:
        return await get_target(db, user, target_id)
    except (TargetNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Target not found.") from exc


async def _safe_lan_call(function: Callable[..., Awaitable[Any]], *args: Any) -> Any:
    try:
        return await function(*args)
    except LanMonitoringDisabledError as exc:
        raise HTTPException(
            status_code=409, detail="LAN monitoring is disabled."
        ) from exc
    except LanServiceCheckDisabledError as exc:
        raise HTTPException(
            status_code=409,
            detail="Authorized service checks are disabled by configuration.",
        ) from exc
    except LanConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LanAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LAN asset not found.") from exc
    except LanDiscoveryRateLimitedError as exc:
        raise HTTPException(
            status_code=429,
            detail="LAN discovery is rate limited. Wait for the configured interval.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.lan operation failed")
        raise _monitoring_unavailable() from exc


async def _safe_baseline_call(
    function: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    try:
        return await function(*args, **kwargs)
    except VulnerabilityBaselineDisabledError as exc:
        raise HTTPException(
            status_code=409, detail="Vulnerability baseline monitoring is disabled."
        ) from exc
    except VulnerabilityBaselineFindingNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Vulnerability baseline finding not found."
        ) from exc
    except LanAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LAN asset not found.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.vulnerability_baseline operation failed")
        raise _monitoring_unavailable() from exc


async def _safe_history_call(
    function: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    try:
        return await function(*args, **kwargs)
    except MonitoringChangeNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Monitoring change not found."
        ) from exc
    except MonitoringHistoryAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LAN asset not found.") from exc
    except MonitoringChangeAlreadyAcknowledgedError as exc:
        raise HTTPException(
            status_code=409, detail="Monitoring change is already acknowledged."
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.history operation failed")
        raise _monitoring_unavailable() from exc


async def _safe_triage_call(
    function: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    try:
        return await function(*args, **kwargs)
    except MonitoringTriageNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Monitoring alert not found."
        ) from exc
    except MonitoringTriageOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=422, detail="The selected owner is not active."
        ) from exc
    except MonitoringTriageValidationError as exc:
        raise HTTPException(
            status_code=422, detail="That triage transition requires more information."
        ) from exc
    except MonitoringTriageConflictError as exc:
        raise HTTPException(
            status_code=409, detail="The alert is already in that lifecycle state."
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="You are not allowed to perform that triage action."
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.triage operation failed")
        raise _monitoring_unavailable() from exc


async def _safe_agent_credential(
    db: AsyncSession,
    provided: str | None,
    ip_address: str | None = None,
    asset_id: uuid.UUID | None = None,
) -> Any:
    try:
        return await validate_agent_credential(db, provided, ip_address, asset_id)
    except AgentCredentialError as exc:
        if exc.reason == "disabled":
            raise HTTPException(
                status_code=503, detail="LAN endpoint telemetry is disabled."
            ) from exc
        raise HTTPException(
            status_code=401, detail="Invalid or inactive endpoint agent token."
        ) from exc


async def _safe_agent_management_call(
    function: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    try:
        return await function(*args, **kwargs)
    except AgentManagementNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Monitoring management resource not found."
        ) from exc
    except AgentManagementConflictError as exc:
        if str(exc) in {"expiration", "cidr", "secret"}:
            raise HTTPException(
                status_code=422,
                detail="The submitted monitoring configuration is invalid.",
            ) from exc
        raise HTTPException(
            status_code=409,
            detail="The monitoring management change conflicts with current state.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.agent_management operation failed")
        raise _monitoring_unavailable() from exc


async def _safe_posture_call(
    function: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    try:
        return await function(*args, **kwargs)
    except EndpointPostureNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Endpoint posture or LAN asset not found."
        ) from exc
    except EndpointRecommendationNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Endpoint recommendation not found."
        ) from exc
    except EndpointRecommendationConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="The endpoint recommendation is already in that lifecycle state.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.endpoint_posture operation failed")
        raise _monitoring_unavailable() from exc
