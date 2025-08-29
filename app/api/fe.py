from fastapi import APIRouter, HTTPException
from app.repo.fe_repo import get_fe_envelope_by_feature_id

router = APIRouter(prefix="/fe", tags=["fe"])

@router.get("/{feature_id}")
async def get_fe_envelope(feature_id: str):
    doc = await get_fe_envelope_by_feature_id(feature_id)
    if not doc:
        raise HTTPException(status_code=404, detail="FEEnvelope not found")
    return doc