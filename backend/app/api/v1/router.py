from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analysis,
    analytics,
    auth,
    case_closure,
    case_management,
    case_review,
    collaboration,
    data_quality,
    engagements,
    findings,
    intelligence,
    investigations,
    iocs,
    knowledge,
    monitoring,
    notifications,
    operations,
    playbooks,
    productivity,
    recon,
    release,
    reports,
    search,
    targets,
    threat_intel,
    threat_workspace,
    timeline,
    users,
)

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(analysis.router)
api_router.include_router(analytics.router)
api_router.include_router(auth.router)
api_router.include_router(case_closure.router)
api_router.include_router(case_review.router)
api_router.include_router(case_management.router)
api_router.include_router(collaboration.router)
api_router.include_router(data_quality.router)
api_router.include_router(engagements.router)
api_router.include_router(users.router)
api_router.include_router(findings.router)
api_router.include_router(intelligence.router)
api_router.include_router(operations.router)
api_router.include_router(investigations.router)
api_router.include_router(iocs.router)
api_router.include_router(knowledge.router)
api_router.include_router(monitoring.router)
api_router.include_router(notifications.router)
api_router.include_router(playbooks.router)
api_router.include_router(productivity.router)
api_router.include_router(targets.router)
api_router.include_router(recon.router)
api_router.include_router(release.router)
api_router.include_router(reports.router)
api_router.include_router(search.router)
api_router.include_router(search.saved_views_router)
api_router.include_router(threat_intel.router)
api_router.include_router(threat_workspace.router)
api_router.include_router(timeline.router)
