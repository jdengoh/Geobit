"""
Pydantic Schemas for Agent State and Context.
"""

from typing import Optional, List

from pydantic import BaseModel

from schemas.reviews import DecisionRecord

from .analysis import AnalysisFindings, AnalysisPlan, Evidence

from .jargons import JargonQueryResult


class StateContext(BaseModel):
    """Context object for carrying state through the pipeline."""
    
    # Defaults?
    data_type: Optional[str] = None

    # Self-declared
    session_id: str
    current_agent: str
    feature_name: Optional[str] = None
    feature_description: Optional[str] = None
    jargon_translation: Optional[JargonQueryResult] = None
    analysis_plan: Optional[AnalysisPlan] = None
    retrieved_evidence: List[Evidence] = []
    analysis_findings: Optional[AnalysisFindings] = None
    decision_record: Optional[DecisionRecord] = None
