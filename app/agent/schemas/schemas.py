from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

HITLAction = Literal["approve", "reject"]

class ReviewCreate(BaseModel):
    feature_id: str
    action: HITLAction
    reason: str = Field(min_length=1)
    reviewer: Optional[str] = None  # email or name (optional)
    session_id: Optional[str] = None

class ReviewOut(ReviewCreate):
    id: str
    created_at: datetime