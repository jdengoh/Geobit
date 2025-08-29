from typing import List, Literal,Optional
from pydantic import BaseModel, Field
from datetime import datetime

DecisionType = Literal["auto_approve","approve_with_conditions","requires_regulation","insufficient_info"]
HITLAction = Literal["approve", "reject"]
class DecisionRecord(BaseModel):
    decision: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str
    conditions: List[str] = []
    citations: List[str] = []
    hitl_recommended: bool = False
    hitl_reasons: List[str] = []

class ReviewCreate(BaseModel):
    feature_id: str
    action: HITLAction
    reason: str = Field(min_length=1)
    reviewer: Optional[str] = None  # email or name (optional)
    session_id: Optional[str] = None

class ReviewOut(ReviewCreate):
    id: str
    created_at: datetime    