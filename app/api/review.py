from fastapi import APIRouter, HTTPException
from app.agent.schemas.reviews import ReviewCreate, ReviewOut
from app.repo.review_repo import insert_review, list_reviews_by_feature
from app.repo.fe_repo import apply_hitl_to_fe
from datetime import datetime
router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.post("", response_model=ReviewOut)
async def create_review(body: ReviewCreate):
    # 1) persist review
    rid = await insert_review(body.model_dump())
    # 2) mark FEEnvelope as human-reviewed (+ adjust UI compliance flag)
    await apply_hitl_to_fe(body.feature_id, body.action, body.reason, body.reviewer)

    return ReviewOut(
        id=rid,
        **body.model_dump(),
        created_at= datetime.now()
    )

@router.get("/by-feature/{feature_id}")
async def get_reviews_by_feature(feature_id: str):
    return await list_reviews_by_feature(feature_id)