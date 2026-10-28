"""
Lead Capture route (NTH-4).
Receives structured lead submissions and lists captured leads.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from src.orchestration.schemas import LeadSubmission
from src.storage.db import db_manager

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("", response_model=Dict[str, Any])
async def submit_lead(lead: LeadSubmission) -> Dict[str, Any]:
    """Save a patient inquiry lead."""
    try:
        lead_id = db_manager.save_lead(lead)
        return {"status": "success", "lead_id": lead_id, "message": "Lead recorded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[LeadSubmission])
async def list_leads() -> List[LeadSubmission]:
    """Retrieve all submitted patient leads."""
    try:
        return db_manager.get_leads()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
