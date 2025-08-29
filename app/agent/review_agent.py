from __future__ import annotations
import json, math, re
from typing import List, Set, Tuple
from urllib.parse import urlparse

from agents import Agent, Runner, RunContextWrapper
from schemas.agents import StateContext
from schemas.analysis import AnalysisFindings, Evidence, Finding, OpenQuestion
from schemas.reviews import DecisionRecord

# ----------------- Config: knobs for consistency -----------------
ENFORCE_HITL: bool = False                # True => any blocking question forces HITL/insufficient_info
ALLOW_CONDITION_SUBSTITUTION: bool = True # convert non-policy blockers into conditions when optimistic
MAX_CITATIONS: int = 8

# trust weights for evidence
DOC_TRUST, GOV_TRUST, EDU_TRUST, NEWS_TRUST, WEB_TRUST = 0.70, 0.85, 0.65, 0.55, 0.45
APPROVE_W, REJECT_W, UNCERTAIN_W = +1.0, -1.0, 0.0

# thresholds on *final* approve/reject after blocker penalty
REQUIRES_REGULATION_IF_REJECT_GE = 0.75
AUTO_APPROVE_IF_APPROVE_GE       = 0.75
APPROVE_WITH_CONDITIONS_MIN      = 0.45

# blocker penalties per category (multiplied by 1.0 if blocking else 0.3)
CATEGORY_BASE = {"policy": 1.00, "data": 0.80, "eng": 0.60, "product": 0.50}

# ----------------- Helpers -----------------
def _domain(url: str) -> str:
    try: return urlparse(url).netloc.lower()
    except: return ""

def _trust_for_evidence(ev: Evidence) -> float:
    if ev.kind == "doc": return DOC_TRUST
    d = _domain(ev.ref)
    if d.endswith(".gov") or "ftc.gov" in d or "europa.eu" in d or "oag.utah.gov" in d: return GOV_TRUST
    if d.endswith(".edu"): return EDU_TRUST
    if any(n in d for n in ("reuters","bloomberg","apnews","nytimes")): return NEWS_TRUST
    return WEB_TRUST

def _finding_strength(f: Finding) -> float:
    if not f.evidence: return 0.35
    trusts = [_trust_for_evidence(ev) for ev in f.evidence]
    base = sum(trusts)/max(1,len(trusts))
    bonus = min(0.30, 0.10 * max(0, len(f.evidence)-1))
    return min(1.0, base + bonus)

def _dir_weight(s: str) -> float:
    s = (s or "").lower()
    if s == "approve": return APPROVE_W
    if s == "reject":  return REJECT_W
    return UNCERTAIN_W

def _collect_citations(evidence: List[Evidence], limit: int) -> List[str]:
    out, seen = [], set()
    for ev in evidence:
        key = f"{ev.kind}:{ev.ref}"
        if key in seen: continue
        seen.add(key); out.append(ev.ref)
        if len(out) >= limit: break
    return out

def _sigmoid(x: float) -> float:
    return 1/(1 + math.exp(-3.0*x))

# ----------------- Deterministic scoring (findings + open questions) -----------------
def _score_findings(af: AnalysisFindings) -> Tuple[float,float,List[Evidence]]:
    approve, reject = 0.0, 0.0
    used_evidence: List[Evidence] = []
    for f in af.findings or []:
        w = _dir_weight(f.supports)
        if w == 0.0: continue
        strength = _finding_strength(f)
        signed = w * strength
        if signed > 0: approve += signed
        else:          reject  += -signed
        used_evidence.extend(f.evidence or [])
    return min(1.0, approve), min(1.0, reject), used_evidence

def _blocker_penalty(af: AnalysisFindings) -> Tuple[float, bool, List[OpenQuestion]]:
    """
    Penalty ∈ [0,1]. Any blocking question flips the `has_blocking` flag.
    """
    penalty = 0.0
    has_blocking = False
    qs = af.open_questions or []
    for q in qs:
        cat = (q.category or "eng").lower()
        base = CATEGORY_BASE.get(cat, 0.60)
        mult = 1.0 if q.blocking else 0.3
        penalty += base * mult
        if q.blocking: has_blocking = True
    # squash multiple questions into [0..1]
    penalty = min(1.0, penalty/2.5)  # tune divisor to your dataset
    return penalty, has_blocking, qs

def _apply_penalty(approve: float, reject: float, penalty: float) -> Tuple[float,float]:
    # Penalty reduces approve first; residual (if large) increases reject a bit
    a = max(0.0, approve * (1.0 - penalty))
    r = min(1.0, reject + max(0.0, penalty - 0.4) * 0.5)
    return a, r

def _conditions_for_open_questions(qs: List[OpenQuestion]) -> List[str]:
    out: List[str] = []
    for q in qs:
        txt = (q.text or "").lower()
        cat = (q.category or "eng").lower()
        if "consent" in txt or cat == "policy":
            out.append("Maintain verifiable parental consent and revocation flow for minors.")
        if "age" in txt:
            out.append("Implement robust age verification (primary + fallback checks).")
        if "retention" in txt or "minimi" in txt:
            out.append("Enforce data minimization and time-bound retention for minors' data.")
        if "access" in txt or "rbac" in txt or cat == "data":
            out.append("Restrict access via RBAC and least-privilege for child data paths.")
        if "audit" in txt or "trace" in txt or cat == "eng":
            out.append("Enable audit logging for enforcement decisions and data access.")
        if "geo" in txt or "jurisdiction" in txt or cat == "product":
            out.append("Validate geo-targeting logic per jurisdiction prior to rollout.")
    # de-dupe, cap
    seen, dedup = set(), []
    for c in out:
        if c in seen: continue
        seen.add(c); dedup.append(c)
        if len(dedup) >= 6: break
    return dedup

# ----------------- LLM prompt -----------------
def reviewer_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return """
You are the Compliance Reviewer. Decide a verdict from structured analysis findings.

FEATURE_DESC: {{feature_desc}}
ANALYSIS_FINDINGS_JSON: {{findings_json}}

Return STRICT JSON:
{
  "decision": "auto_approve" | "approve_with_conditions" | "requires_regulation" | "insufficient_info",
  "confidence": 0.0-1.0,
  "justification": "1-3 short sentences summarizing why",
  "conditions": ["..."],
  "citations": ["..."],
  "hitl_recommended": false,
  "hitl_reasons": []
}

Guidance:
- Prefer "auto_approve" if approve-leaning findings clearly dominate.
- Use "approve_with_conditions" if mostly positive but specific safeguards are required.
- Use "requires_regulation" if reject signals are strong.
- Use "insufficient_info" only if evidence/findings are too sparse or contradictory.
- Derive citations ONLY from the evidence in ANALYSIS_FINDINGS_JSON.
""".strip()

def create_llm_reviewer() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Reviewer (LLM)",
        instructions=reviewer_prompt,
        tools=[],
        output_type=DecisionRecord,
        model="gpt-5-nano",  # don't pass temperature/top_p
    )

# ----------------- Guardrails & alignment -----------------
def _align_to_rules(llm: DecisionRecord, af: AnalysisFindings) -> DecisionRecord:
    # 1) deterministic scores
    approve, reject, used_evs = _score_findings(af)
    penalty, has_blocking, qs = _blocker_penalty(af)
    approve_adj, reject_adj = _apply_penalty(approve, reject, penalty)

    # 2) strict-mode HITL
    if ENFORCE_HITL and has_blocking:
        llm.decision = "insufficient_info"
        llm.hitl_recommended = True
        llm.hitl_reasons = ["Blocking open questions present."]
    else:
        # 3) deterministic verdict
        if reject_adj >= REQUIRES_REGULATION_IF_REJECT_GE:
            llm.decision = "requires_regulation"
        elif approve_adj >= AUTO_APPROVE_IF_APPROVE_GE:
            llm.decision = "auto_approve"
        elif approve_adj >= APPROVE_WITH_CONDITIONS_MIN:
            llm.decision = "approve_with_conditions"
        else:
            llm.decision = "insufficient_info"

        # 4) optimistic: convert some blockers to conditions
        if not ENFORCE_HITL and ALLOW_CONDITION_SUBSTITUTION and qs:
            added = _conditions_for_open_questions(qs)
            # merge LLM conditions with generated
            have = set(llm.conditions or [])
            for c in added:
                if c not in have:
                    llm.conditions.append(c)

    # 5) citations must be real
    all_ev = [ev for f in (af.findings or []) for ev in (f.evidence or [])]
    valid = set([ev.ref for ev in all_ev])
    llm.citations = [c for c in (llm.citations or []) if c in valid]
    if not llm.citations:
        llm.citations = _collect_citations(all_ev, MAX_CITATIONS)

    # 6) clamp confidence based on margin, not just LLM
    margin = approve_adj - reject_adj
    algo_conf = _sigmoid(margin)
    llm.confidence = round(0.5*llm.confidence + 0.5*algo_conf, 3)

    # 7) ensure conditions present when required
    if llm.decision == "approve_with_conditions" and not llm.conditions:
        llm.conditions = ["Operate safeguards documented in analysis findings."]

    # 8) keep optimistic (HITL off) unless strict-mode already set it
    if not ENFORCE_HITL:
        llm.hitl_recommended = False
        llm.hitl_reasons = []

    return llm

# ----------------- Public entry -----------------
async def run_reviewer(ctx: StateContext) -> DecisionRecord:
    if not ctx.analysis_findings:
        raise ValueError("Reviewer: ctx.analysis_findings is missing")

    feature_desc = ctx.feature_description or ""
    findings_json = json.dumps(ctx.analysis_findings.model_dump(), sort_keys=True)

    agent = create_llm_reviewer()
    prompt = (reviewer_prompt(None, None)
              .replace("{{feature_desc}}", feature_desc)
              .replace("{{findings_json}}", findings_json))
    res = await Runner.run(agent, prompt, context=ctx)

    verdict = _align_to_rules(res.final_output, ctx.analysis_findings)
    ctx.decision_record = verdict
    return verdict

# ----------------- Local demo -----------------
if __name__ == "__main__":
    import asyncio
    from schemas.analysis import AnalysisFindings, Finding, Evidence, OpenQuestion

    af = AnalysisFindings(
        findings=[
            Finding(
                key_point="Parental consent is required and implemented.",
                supports="approve",
                evidence=[Evidence(kind="doc", ref="doc:utah_act#p12", snippet="..."),
                          Evidence(kind="web", ref="https://ftc.gov/child-privacy", snippet="...")]
            ),
            Finding(
                key_point="Curfew restriction is valid if geo+age gating enforced.",
                supports="approve",
                evidence=[Evidence(kind="doc", ref="doc:utah_curfew#p3", snippet="...")]
            ),
            # Finding(key_point="Retention unclear for minors' data.", supports="reject", evidence=[]),
        ],
        open_questions=[
            OpenQuestion(text="How will age be verified across CustomAPI and XRAY?", category="eng", blocking=False),
            OpenQuestion(text="What are the parental consent revocation flows?", category="policy", blocking=True),
        ],
    )
    ctx = StateContext(session_id="demo-rev-llm-oq-001", current_agent="reviewer", analysis_findings=af, feature_description="Utah curfew demo")
    print(asyncio.run(run_reviewer(ctx)).model_dump())