"""
Reviewer Agent (LLM + Deterministic Guardrails)

PURPOSE
-------
Takes AnalysisFindings (from Synthesizer) and produces a final reviewer verdict:
  - "requires_regulation"      => YES, geo-specific compliance is clearly needed
  - "approve_with_conditions"  => YES, but proceed if conditions are met
  - "auto_approve"             => NO, geo-specific compliance not required
  - "insufficient_info"        => Unknown / send to Human-In-The-Loop (HITL)

WHAT THIS CODE DOES (FLOW)
--------------------------
1) We prompt a small LLM ('gpt-5-nano') with the structured AnalysisFindings as JSON.
2) We compute deterministic scores from the same findings:
     - Trust-weight evidence, convert each Finding.supports ("approve"/"reject"/"uncertain")
       into signed contributions, and aggregate.
     - Apply a penalty from open_questions (blocking > non-blocking).
     - Map final adjusted scores to a verdict via thresholds.
3) We ALIGN the LLM's JSON verdict with the deterministic outcome:
     - If strong approve-signal => "requires_regulation"
     - If strong reject-signal  => "auto_approve"
     - Else if moderate approve => "approve_with_conditions"
     - Else                     => "insufficient_info"
   We also normalize citations and merge auto-generated conditions.

HOW IT DECIDES *WITHOUT* HITL
-----------------------------
- HITL is OFF by default (ENFORCE_HITL=False).
- Even if there are open questions, we try to proceed optimistically:
  * Non-blocking questions may become CONDITIONS (if ALLOW_CONDITION_SUBSTITUTION=True).
  * Blocking questions still push confidence down via penalty, but do not stop the run
    unless you flip ENFORCE_HITL=True (strict mode).

WHERE TO INTEGRATE HITL (HUMAN REVIEW)
--------------------------------------
A) Strict Gate (flip a switch):
   - Set ENFORCE_HITL=True to force "insufficient_info" whenever any blocking question exists.
B) Conditional Gate (common pattern):
   - If verdict.confidence < threshold (e.g., 0.6) OR there are blocking open questions,
     emit a HITL ticket and stop the run.
   - Provided helper stubs:
       _should_trigger_hitl(...) -> bool
       _emit_hitl_ticket(...)    -> enqueue/save a task (Slack/Jira/DB)

AFTER HITL COMES BACK
---------------------
- Collect human resolutions (e.g., “age verification is implemented with vendor X”).
- Convert them into either:
    * new CONDITIONS to attach,
    * or Finding adjustments (e.g., "uncertain" -> "approve"),
    * and/or mark an open question as resolved (non-blocking).
- Call `apply_hitl_resolutions(af, resolutions)` then re-run `run_reviewer(ctx)`.

AUDIT TRAIL
-----------
- Save in DB at each step:
   - analysis_findings, reviewer_input_prompt, llm_output_raw, deterministic_debug,
     final DecisionRecord + reasons/citations/conditions, any HITL tickets and resolutions.

TEAM CONTRACT (frontend mapping)
--------------------------------
- "requires_regulation" / "approve_with_conditions" => FE "compliant"
- "auto_approve"                                    => FE "no-compliance"
- "insufficient_info"                               => FE "needs-review"
"""

from __future__ import annotations
import json, math, re
from typing import List, Set, Tuple, Optional, Literal
from urllib.parse import urlparse

from agents import Agent, Runner, RunContextWrapper
from app.agent.schemas.agents import StateContext
from app.agent.schemas.analysis import AnalysisFindings, Evidence, Finding, OpenQuestion
from app.agent.schemas.reviews import DecisionRecord

# ----------------- Config: knobs for consistency -----------------
ENFORCE_HITL: bool = False                # True => any blocking question forces HITL/insufficient_info
ALLOW_CONDITION_SUBSTITUTION: bool = True # convert non-policy blockers into conditions when optimistic
MAX_CITATIONS: int = 8

# trust weights for evidence
DOC_TRUST, GOV_TRUST, EDU_TRUST, NEWS_TRUST, WEB_TRUST = 0.70, 0.85, 0.65, 0.55, 0.45
APPROVE_W, REJECT_W, UNCERTAIN_W = +1.0, -1.0, 0.0

# thresholds on *final* approve/reject after blocker penalty
REQUIRES_REGULATION_IF_APPROVE_GE = 0.75   # YES: strong approval => regulation required
AUTO_APPROVE_IF_REJECT_GE         = 0.75   # NO:  strong rejection => auto-approve (no compliance)
APPROVE_WITH_CONDITIONS_MIN       = 0.45

# blocker penalties per category (multiplied by 1.0 if blocking else 0.3)
CATEGORY_BASE = {"policy": 1.00, "data": 0.80, "eng": 0.60, "product": 0.50}

# -------------- Optional: HITL resolution model (for later) --------------
# If you want to record human feedback formally and re-run the reviewer,
# you can pass a list[HITLResolution] into apply_hitl_resolutions(...).
class HITLResolution:  # keep it simple here (or move to schemas.reviews)
    question_text: str
    resolution: Literal["approve", "reject", "condition", "drop"]
    note: Optional[str] = None

# ----------------- Helpers -----------------
def _domain(url: str) -> str:
    try: return urlparse(url).netloc.lower()
    except: return ""

def _trust_for_evidence(ev: Evidence) -> float:
    """
    Assign a trust score per evidence type/domain. 'doc' is your KB doc,
    .gov/europa.eu is high, .edu and reputable news slightly lower, else web.
    """
    if ev.kind == "doc": return DOC_TRUST
    d = _domain(ev.ref)
    if d.endswith(".gov") or "ftc.gov" in d or "europa.eu" in d or "oag.utah.gov" in d: return GOV_TRUST
    if d.endswith(".edu"): return EDU_TRUST
    if any(n in d for n in ("reuters","bloomberg","apnews","nytimes")): return NEWS_TRUST
    return WEB_TRUST

def _finding_strength(f: Finding) -> float:
    """
    Strength ~ average trust of its evidence (+ small bonus for >1 citations).
    """
    if not f.evidence: return 0.35
    trusts = [_trust_for_evidence(ev) for ev in f.evidence]
    base = sum(trusts)/max(1,len(trusts))
    bonus = min(0.30, 0.10 * max(0, len(f.evidence)-1))
    return min(1.0, base + bonus)

def _dir_weight(s: str) -> float:
    """
    Convert supports label into a direction:
      approve => +1 (YES needs geo compliance)
      reject  => -1 (NO  needs geo compliance)
      uncertain => 0
    """
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
    """
    Aggregate approve/reject strength from findings into [0..1] each.
    Returns (approve_score, reject_score, used_evidence)
    """
    approve, reject = 0.0, 0.0
    used_evidence: List[Evidence] = []
    for f in af.findings or []:
        w = _dir_weight(f.supports)
        if w == 0.0: 
            continue
        strength = _finding_strength(f)
        signed = w * strength
        if signed > 0: approve += signed
        else:          reject  += -signed
        used_evidence.extend(f.evidence or [])
    return min(1.0, approve), min(1.0, reject), used_evidence

def _blocker_penalty(af: AnalysisFindings) -> Tuple[float, bool, List[OpenQuestion]]:
    """
    Compute penalty ∈ [0,1] from open questions.
    Any blocking question flips `has_blocking=True`.
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
    """
    Penalty reduces approve first (we're conservative),
    then (if large) adds a bit to reject to reflect uncertainty.
    """
    a = max(0.0, approve * (1.0 - penalty))
    r = min(1.0, reject + max(0.0, penalty - 0.4) * 0.5)
    return a, r

def _conditions_for_open_questions(qs: List[OpenQuestion]) -> List[str]:
    """
    Turn common open questions into standardized conditions
    (so FE & Ops can act consistently).
    """
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
- Prefer "requires_regulation" if APPROVE-leaning findings clearly dominate (i.e., evidence supports that geo-specific compliance is required).
- Use "approve_with_conditions" if mostly positive but specific safeguards/conditions are needed.
- Prefer "auto_approve" if REJECT-leaning findings clearly dominate (i.e., evidence refutes the need for geo-specific compliance).
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
    """
    Align LLM output to deterministic scores:
    - Score findings (approve/reject), compute penalty from open questions,
      derive adjusted scores, and map to a verdict via thresholds.
    - Normalize citations and merge auto-conditions if allowed.
    """
    # 1) deterministic scores
    approve, reject, used_evs = _score_findings(af)
    penalty, has_blocking, qs = _blocker_penalty(af)
    approve_adj, reject_adj = _apply_penalty(approve, reject, penalty)

    # 2) strict-mode HITL (hard gate)
    if ENFORCE_HITL and has_blocking:
        llm.decision = "insufficient_info"
        llm.hitl_recommended = True
        llm.hitl_reasons = ["Blocking open questions present."]
    else:
        # 3) deterministic verdict (corrected mapping)
        if approve_adj >= REQUIRES_REGULATION_IF_APPROVE_GE:
            llm.decision = "requires_regulation"
        elif reject_adj >= AUTO_APPROVE_IF_REJECT_GE:
            llm.decision = "auto_approve"
        elif approve_adj >= APPROVE_WITH_CONDITIONS_MIN:
            llm.decision = "approve_with_conditions"
        else:
            llm.decision = "insufficient_info"

        # 4) optimistic: convert some blockers to conditions
        if not ENFORCE_HITL and ALLOW_CONDITION_SUBSTITUTION and qs:
            added = _conditions_for_open_questions(qs)
            have = set(llm.conditions or [])
            for c in added:
                if c not in have:
                    llm.conditions.append(c)

    # 5) citations must be real (subset of provided evidence)
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

    # 9) (Optional) expose debug to ctx if you want (margin, penalty, adj scores)
    #    -> Log to Mongo for audit or surface in an admin panel.

    return llm

# ----------------- HITL hooks (stubs for your colleague) -----------------
def _should_trigger_hitl(verdict: DecisionRecord, has_blocking: bool, min_conf: float = 0.6) -> bool:
    """
    Recommended: route to HITL if confidence is low OR there are blocking questions.
    This is separate from ENFORCE_HITL, which hard-stops earlier.
    """
    return has_blocking or (verdict.confidence is not None and verdict.confidence < min_conf)

async def _emit_hitl_ticket(ctx: StateContext, reason: str) -> None:
    """
    TODO: Wire this to your system:
      - Create 'review_tasks' document in Mongo
      - Or push to Slack/Jira/Queue with ctx.session_id, feature_name/desc,
        ctx.analysis_findings, and the reviewer draft verdict.
    """
    # Example placeholder:
    # await mongo.review_tasks.insert_one({
    #   "session_id": ctx.session_id,
    #   "feature_name": ctx.feature_name,
    #   "feature_desc": ctx.feature_description,
    #   "analysis_findings": ctx.analysis_findings.model_dump(),
    #   "reason": reason,
    #   "status": "pending",
    # })
    return None

def apply_hitl_resolutions(af: AnalysisFindings, resolutions: List[HITLResolution]) -> AnalysisFindings:
    """
    OPTIONAL: mutate/return a new AnalysisFindings after human feedback.
    Typical actions:
      - resolution="condition": convert related open question to a condition (remove it from open_questions)
      - resolution="approve"/"reject": add a small Finding with that supports label and a short note
      - resolution="drop": remove an irrelevant open question
    """
    # No-op placeholder; implement how you want to map resolutions back into AF.
    return af

# ----------------- Public entry -----------------
async def run_reviewer(ctx: StateContext) -> DecisionRecord:
    """
    Main entry:
      - Build LLM prompt from ctx.analysis_findings
      - Align LLM output with deterministic rules
      - Optionally emit a HITL ticket (hook)
    """
    if not ctx.analysis_findings:
        raise ValueError("Reviewer: ctx.analysis_findings is missing")

    feature_desc = ctx.feature_description or ""
    findings_json = json.dumps(ctx.analysis_findings.model_dump(), sort_keys=True)

    agent = create_llm_reviewer()
    prompt = (reviewer_prompt(None, None)
              .replace("{{feature_desc}}", feature_desc)
              .replace("{{findings_json}}", findings_json))
    res = await Runner.run(agent, prompt, context=ctx)

    # Align with rules
    verdict = _align_to_rules(res.final_output, ctx.analysis_findings)

    # HITL integration point (soft gate): emit ticket if confidence low or blockers present
    penalty, has_blocking, _ = _blocker_penalty(ctx.analysis_findings)
    if _should_trigger_hitl(verdict, has_blocking):
        verdict.hitl_recommended = True
        verdict.hitl_reasons = verdict.hitl_reasons or []
        verdict.hitl_reasons.append("Low confidence or unresolved blocking question(s).")
        # Fire-and-forget (or await) your queue/save here:
        await _emit_hitl_ticket(ctx, reason="reviewer_soft_gate")

    ctx.decision_record = verdict
    return verdict

# ----------------- Local demo -----------------
if __name__ == "__main__":
    import asyncio
    from schemas.analysis import AnalysisFindings, Finding, Evidence, OpenQuestion

    af = AnalysisFindings(
       findings=[
            Finding(
                key_point="Utah law requires parental consent and allows curfew-style protections for minors.",
                supports="approve",
                evidence=[
                    Evidence(kind="doc", ref="doc:utah_social_media_act#p12",
                             snippet="Utah law requires parental consent and permits curfew protections for minors.")
                ],
            ),
            Finding(
                key_point="Curfew restrictions must be enforced via age verification and Utah targeting.",
                supports="approve",
                evidence=[
                    Evidence(kind="doc", ref="doc:utah_curfew_guidance#p3",
                             snippet="Curfew-based restrictions must use age verification and Utah jurisdiction targeting.")
                ],
            ),
            Finding(
                key_point="FTC guidance emphasizes parental consent and safeguards for minors.",
                supports="uncertain",
                evidence=[
                    Evidence(kind="web", ref="https://ftc.gov/child-privacy",
                             snippet="FTC guidance highlights parental consent and minor safeguards.")
                ],
            ),
        ],
        open_questions=[
            OpenQuestion(
                text="FTC guidance is not geo-specific and does not explicitly mandate geo-targeting or geo-based curfew logic; does it affect the need for geo-specific compliance?",
                category="policy",
                blocking=False,
            ),
        ],
    )

    ctx = StateContext(
        session_id="demo-rev-llm-oq-001",
        current_agent="reviewer",
        analysis_findings=af,
        feature_description="Utah curfew demo",
    )

    print(asyncio.run(run_reviewer(ctx)).model_dump())