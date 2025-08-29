# app/api/hitl.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.repo.fe_repo import list_by_session, get_one

router = APIRouter(prefix="/hitl", tags=["hitl"])

@router.get("/runs/{session_id}")
async def get_run(session_id: str):
    """Return all FEEnvelopes for a session (latest first)."""
    return await list_by_session(session_id)

@router.get("/decisions/{db_id}")
async def get_decision(db_id: str):
    doc = await get_one(db_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc