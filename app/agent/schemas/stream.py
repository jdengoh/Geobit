from pydantic import BaseModel
from typing import Any, List, Optional

class StreamEvent(BaseModel):
    event: str                     # "status" | "stage" | "final" | "error"
    stage: Optional[str] = None    # e.g. "pre_scan" | "jargon" | "analysis" | "review" | "summarise"
    message: Optional[str] = None  # human-friendly progress line
    payload: Optional[Any] = None  # stage-specific info
    terminating: bool = False      # True for the last event only

# Frontend envelope (exactly what FE needs)
class FEUI(BaseModel):
    complianceFlag: str            # "compliant" | "no-compliance" | "needs-review"
    reviewedStatus: str            # "auto" | "pending" | "human-reviewed"
    regulationTag: Optional[str] = None

class FEEnvelope(BaseModel):
    feature_id: str               # UUID as string (stable key)
    session_id: Optional[str] = None 
    db_id: Optional[str] = None       
    standardized_name: str
    standardized_description: str
    decision: str
    confidence: float
    justification: str
    conditions: List[str] = []
    citations: List[str] = []
    open_questions: List[dict] = []
    terminating: bool = True
    ui: FEUI