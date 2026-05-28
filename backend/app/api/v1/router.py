from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analysis,
    auth,
    findings,
    investigations,
    knowledge,
    recon,
    reports,
    targets,
    threat_intel,
    users,
)

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(analysis.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(findings.router)
api_router.include_router(investigations.router)
api_router.include_router(knowledge.router)
api_router.include_router(targets.router)
api_router.include_router(recon.router)
api_router.include_router(reports.router)
api_router.include_router(threat_intel.router)
