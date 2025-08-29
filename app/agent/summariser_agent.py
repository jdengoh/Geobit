"""
Summariser Agent
- Purpose: Convert Reviewer DecisionRecord (+ context) → FEEnvelope for the frontend.
- No LLM here: deterministic formatting + light heuristics for UI flags and regulation tag.
- Call this AFTER the Reviewer has written ctx.decision_record.
"""

from __future__ import annotations
from typing import List, Optional
import re

from pydantic import BaseModel, Field
from app.agent.schemas.agents import StateContext     # your shared pipeline state
from app.agent.schemas.reviews import DecisionRecord  # decision from Reviewer
from app.agent.schemas.analysis import AnalysisFindings

# ---------- Frontend envelope (what FE renders) ----------
class FEUI(BaseModel):
    complianceFlag: str = Field(description='"compliant" | "no-compliance" | "needs-review"')
    reviewedStatus: str = Field(description='"auto" | "pending" | "human-reviewed"')
    regulationTag: Optional[str] = None

class FEEnvelope(BaseModel):
    feature_id: str
    standardized_name: str
    standardized_description: str
    decision: str                   # "requires_regulation" | "approve_with_conditions" | "auto_approve" | "insufficient_info"
    confidence: float
    justification: str
    conditions: List[str] = []
    citations: List[str] = []
    open_questions: List[dict] = []
    terminating: bool = True
    ui: FEUI

# ---------- Helpers ----------
def _map_decision_to_ui(decision: str, hitl: bool) -> FEUI:
    """
    Map Reviewer decision → FE flags:
      - requires_regulation      => "compliant" (YES: geo-specific compliance needed)
      - approve_with_conditions  => "compliant" (YES: needed, but with conditions)
      - auto_approve             => "no-compliance" (NO: not needed)
      - insufficient_info        => "needs-review" (HITL needed)
    """
    decision = (decision or "").lower()
    if decision == "requires_regulation":
        return FEUI(complianceFlag="compliant", reviewedStatus="pending" if hitl else "auto")
    if decision == "approve_with_conditions":
        return FEUI(complianceFlag="compliant", reviewedStatus="pending" if hitl else "auto")
    if decision == "auto_approve":
        return FEUI(complianceFlag="no-compliance", reviewedStatus="auto")
    return FEUI(complianceFlag="needs-review", reviewedStatus="pending")

def _infer_regulation_tag(ctx: StateContext, dr: DecisionRecord) -> Optional[str]:
    """
    Very lightweight heuristics to surface a regulation tag for the table.
    Priority:
      1) Citations (domain/name hints)
      2) Feature text (name/description)
      3) Jargon searched terms (if available)
    """
    text = f"{ctx.feature_name or ''} {ctx.feature_description or ''}".lower()
    cites = (dr.citations or [])

    # 1) From citations
    joined = " ".join(cites).lower()
    if "ftc.gov" in joined or "coppa" in text:
        return "COPPA / FTC"
    if "europa.eu" in joined or "dsa" in text:
        return "EU DSA"
    if "gdpr" in joined:
        return "GDPR"
    if "oag.utah.gov" in joined or "utah" in text:
        return "Utah Social Media Regulation Act"
    m = re.search(r"\b(sb ?\d{3,})\b", text, flags=re.I)
    if m:
        return m.group(1).upper().replace(" ", "")

    # 2) From feature text (fallbacks)
    if "gdpr" in text: return "GDPR"
    if "coppa" in text: return "COPPA / FTC"
    if "dsa" in text or "eu " in text: return "EU DSA"
    if "utah" in text: return "Utah Social Media Regulation Act"

    # 3) From jargon searched_terms if present (optional)
    try:
        jr = ctx.jargon_translation
        if jr and getattr(jr, "searched_terms", None):
            for st in jr.searched_terms:
                term = (getattr(st, "term", "") or "").lower()
                if not term: continue
                if "utah" in term: return "Utah Social Media Regulation Act"
                if "gdpr" in term: return "GDPR"
                if "coppa" in term: return "COPPA / FTC"
                if "digital services act" in term or "dsa" in term: return "EU DSA"
    except Exception:
        pass

    return None

def _serialize_open_questions(af: Optional[AnalysisFindings]) -> List[dict]:
    if not af or not af.open_questions:
        return []
    out = []
    for q in af.open_questions:
        out.append({
            "text": q.text,
            "category": q.category,
            "blocking": bool(q.blocking),
        })
    return out

# ---------- Public API ----------
async def run_summariser(ctx: StateContext) -> FEEnvelope:
    """
    Build the single final object the FE needs to render.
    Pre-req: ctx.decision_record is set by the Reviewer.
    Fallback: if missing, emit an 'insufficient_info' envelope.
    """
    dr: Optional[DecisionRecord] = getattr(ctx, "decision_record", None)
    feature_id = getattr(ctx, "session_id", "unknown-session")
    name = ctx.feature_name or "Untitled Feature"
    desc = ctx.feature_description or ""

    if not dr:
        ui = FEUI(complianceFlag="needs-review", reviewedStatus="pending")
        return FEEnvelope(
            feature_id=feature_id,
            standardized_name=name,
            standardized_description=desc,
            decision="insufficient_info",
            confidence=0.0,
            justification="Reviewer decision missing.",
            conditions=[],
            citations=[],
            open_questions=_serialize_open_questions(getattr(ctx, "analysis_findings", None)),
            terminating=True,
            ui=ui,
        )

    ui = _map_decision_to_ui(dr.decision, bool(dr.hitl_recommended))
    # Try to infer a nice regulation tag for the table
    ui.regulationTag = _infer_regulation_tag(ctx, dr)

    return FEEnvelope(
        feature_id=feature_id,
        standardized_name=name,
        standardized_description=desc,
        decision=dr.decision,
        confidence=round(float(dr.confidence or 0.0), 3),
        justification=dr.justification or "",
        conditions=dr.conditions or [],
        citations=dr.citations or [],
        open_questions=_serialize_open_questions(getattr(ctx, "analysis_findings", None)),
        terminating=True,
        ui=ui,
    )