from typing import Optional, List

from pydantic import BaseModel

from app.agent.schemas.reviews import DecisionRecord

from app.agent.schemas.analysis import AnalysisFindings, AnalysisPlan, Evidence

from app.agent.schemas.jargons import JargonQueryResult

from app.agent.schemas.pre_screen_result import PreScreenResult


class StateContext(BaseModel):
    """Context object for carrying state through the pipeline."""
    
    # Defaults?
    data_type: Optional[str] = None

    # Self-declared
    session_id: str
    current_agent: str
    retrieved_evidence: Optional[List[Evidence]] = None
    feature_name: Optional[str] = None
    feature_description: Optional[str] = None
    jargon_translation: Optional[JargonQueryResult] = None
    analysis_plan: Optional[AnalysisPlan] = None
    retrieved_evidence: List[Evidence] = []
    analysis_findings: Optional[AnalysisFindings] = None
    decision_record: Optional[DecisionRecord] = None
    prescreening_result: Optional[PreScreenResult] = None