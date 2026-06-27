from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.schemas.release import ReleaseMetadataResponse
from app.services.release import get_release_metadata

router = APIRouter(tags=["release"])


@router.get("/release", response_model=ReleaseMetadataResponse)
async def release_metadata(
    db: AsyncSession = Depends(get_db),
) -> ReleaseMetadataResponse:
    return await get_release_metadata(db)
