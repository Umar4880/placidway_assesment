"""
Content Gap Logging route (NTH-5).
Provides visibility into logged unanswered medical travel queries for content teams.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from src.orchestration.schemas import ContentGapItem
from src.storage.db import db_manager

router = APIRouter(prefix="/api/content-gaps", tags=["content-gaps"])


@router.get("", response_model=List[ContentGapItem])
async def list_content_gaps() -> List[ContentGapItem]:
    """Retrieve logged content gaps for audit and coverage expansion."""
    try:
        return db_manager.get_content_gaps()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
