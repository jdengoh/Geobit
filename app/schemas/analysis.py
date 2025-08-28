"""
Schemas used by the Analysis Agent.

Flow overview:
1) Planner outputs AnalysisPlan.retrieval_needs -> sent to Retrieval Agent.
2) Retrieval Agent returns a list of Evidence -> fed into Synthesizer.
3) Synthesizer outputs AnalysisFindings -> used by downstream Report/Reviewer.
"""

from pydantic import BaseModel
from typing import List, Literal

class RetrievalNeed(BaseModel):
    """
    A *targeted search instruction* for the Retrieval Agent.
    - query: human-readable query (the Retrieval Agent can expand/split as needed)
    - must_tags: hard filters the Retrieval Agent must honor (e.g., child_safety)
    - nice_to_have_tags: soft filters; Retrieval Agent can use to rerank
    """
    query: str
    must_tags: List[str] = []
    nice_to_have_tags: List[str] = []

class Evidence(BaseModel):
    """
    One *cited snippet* returned by the Retrieval Agent.
    - kind: 'doc' for KB hits or 'web' for online sources
    - ref: 'doc:{id}#p12' or a URL
    - snippet: short extract containing the relevant claim
    """
    kind: Literal["doc","web"]
    ref: str
    snippet: str

class Finding(BaseModel):
    """
    A *reasoned claim* about the feature, grounded in evidence.
    - key_point: short factual statement
    - supports: how the finding influences compliance decision
      ('approve' reduces risk, 'reject' increases risk, 'uncertain' needs HITL)
    - evidence: list of cited Evidence entries that support this finding
    """
    key_point: str
    supports: Literal["approve","reject","uncertain"]
    evidence: List[Evidence] = []

class AnalysisPlan(BaseModel):
    """
    Planner output. The orchestrator forwards these needs to Retrieval Agent.
    """
    retrieval_needs: List[RetrievalNeed]

class AnalysisFindings(BaseModel):
    """
    Synthesizer output. Downstream components (Reviewer / Report Agent) consume this.
    - findings: structured, citable conclusions
    - open_questions: questions that block a definitive decision (HITL trigger)
    """
    findings: List[Finding]
    open_questions: List[str] = []