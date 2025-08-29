from typing import List, Literal
from pydantic import BaseModel, Field

DecisionType = Literal["auto_approve","approve_with_conditions","requires_regulation","insufficient_info"]

class DecisionRecord(BaseModel):
    decision: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str
    conditions: List[str] = []
    citations: List[str] = []
    hitl_recommended: bool = False
    hitl_reasons: List[str] = []