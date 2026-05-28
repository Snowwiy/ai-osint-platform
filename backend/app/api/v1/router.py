from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, investigations, recon, targets, users

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(investigations.router)
api_router.include_router(targets.router)
api_router.include_router(recon.router)
