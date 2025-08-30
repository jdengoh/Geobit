"""
Analysis Agent (Planner + Synthesizer)

WHERE THIS SITS IN THE PIPELINE
-------------------------------
1) (TODO) Pre-Screen Agent
   - Quickly filters out business-only geofences or “no intent stated” cases
     (e.g., “US-only market test”, “global except KR with no reason”).
   - If PRE-SCREEN says "business-only" or "no-intent", we STOP and do NOT call Analysis.
   - If PRE-SCREEN says "likely legal intent" (or ambiguous), we CONTINUE.

2) Jargon Agent
   - Normalizes acronyms/codenames to clear terms and returns StandardizedFeature + jargon_result.
   - StateContext.jargon_translation is typically filled here (Pydantic model).

3) Analysis Agent (THIS FILE)
   A) Planner:
      - Emits targeted RetrievalNeeds (queries + tags) for legal KB/Web retrieval.
      - Stateless: does NOT fetch sources itself.
   B) Synthesizer:
      - Consumes Evidence[] (returned by Retrieval Agent).
      - Produces AnalysisFindings with structured findings (+ open_questions).

4) Retrieval Agent
   - Uses Planner’s RetrievalNeeds to query KB/Web and returns Evidence[] (doc/web + snippets).

5) Reviewer Agent
   - Consumes AnalysisFindings. Scores evidence, handles blocking logic,
     produces final verdict: requires_regulation | approve_with_conditions | auto_approve | insufficient_info.
   - If open_questions.blocking==True or confidence low, can trigger HITL.
   - NOTE: "blocking" is a signal from Synthesizer to Reviewer/HITL; THIS FILE only emits it.

6) Summarizer Agent
   - Formats final decision for FE + emits a terminating event for the run loop.

KEY DESIGN CHOICES
------------------
- Planner/Synthesizer are stateless specialists (prompt-only).
- All I/O is strict JSON validated by Pydantic (auditable).
- Blocking:
  * Synthesizer can mark open_questions as blocking=True (e.g., unknown jurisdiction).
  * Reviewer interprets blocking as a penalty or a HITL gate (depending on config).

OUTPUTS OF THIS FILE
--------------------
- AnalysisPlan (from Planner): list of retrieval_needs for the Retrieval Agent.
- AnalysisFindings (from Synthesizer): structured findings + open_questions (with blocking flags).
"""

from agents import Agent, Runner, RunContextWrapper
from typing import List, Optional
import json
from app.agent.schemas.jargons import JargonQueryResult
from app.agent.schemas.agents import StateContext
# from app.agent._tagging import jargon_to_tags, derive_text_tags, merge_tag_sets
from app.agent.schemas.analysis import (
    RetrievalNeed,
    Evidence,
    Finding,
    OpenQuestion,
    AnalysisPlan,
    AnalysisFindings,
)

# ---------- PROMPTS ----------
def plan_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    """
    Planner prompt:
    - Receives feature/jargon/tags context.
    - Must return ONLY JSON with 2–5 RetrievalNeeds.
    - 'must_tags' are hard constraints; 'nice_to_have' guide re-ranking.
    """
    return """
You are a Compliance Analysis Planner.

FEATURE_NAME: {{feature_name}}
FEATURE_DESC: {{feature_desc}}
JARGON_JSON: {{jargon_json}}
TAGS_JSON: {{tags_json}}

Create 2–5 targeted retrieval needs for Legal KB and Web.
- must_tags: critical filters (child_safety, age_gating, personalization, jurisdiction_ut)
- nice_to_have_tags: helpful reranking hints
Return ONLY JSON:
{ "retrieval_needs": [ { "query":"...", "must_tags":["..."], "nice_to_have_tags":["..."] } ] }
""".strip()

def synth_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    """
    Synthesizer prompt:
    - Hypothesis framing ensures consistent labels:
      approve   => evidence SUPPORTS that geo-specific compliance IS needed
      reject    => evidence REFUTES  that geo-specific compliance is needed
      uncertain => unclear/weak/conflicting
    - Each evidence item should map to one Finding (with citation).
    - open_questions can be emitted; set blocking=True if the Reviewer
      SHOULD NOT auto-approve without HITL (e.g., missing jurisdiction).
    """
    return """
You are a Compliance Analysis Synthesizer.

HYPOTHESIS: "This feature REQUIRES geo-specific compliance logic."

INTERPRETATION:
- "approve"  = evidence SUPPORTS the hypothesis (YES, geo-compliance IS needed).
- "reject"   = evidence REFUTES  the hypothesis (NO, geo-compliance is NOT needed).
- "uncertain"= unclear or conflicting.

NEGATION & NON-LEGAL CLUES -> "reject":
- Phrases like "no requirement", "not mandated", "no law", "business geofence", "A/B test", "trial rollout", "global/universal feature".

LEGAL/REGULATORY CLUES -> "approve":
- Law/regulator signal ("Act", "Regulation", "Law", "Directive", "GDPR", "COPPA", "DSA", "SBxxx"), .gov / europa.eu domains, internal doc refs tagged to laws (e.g., "doc:*act", "doc:*law").

REQUIRED BEHAVIOR:
1) Classify EACH evidence item into exactly one finding with supports="approve"|"reject"|"uncertain".
2) Summarize the key point for that evidence in "key_point".
3) Use the provided EVIDENCE_JSON verbatim for citations (kind/ref/snippet).
4) If any evidence appears irrelevant, include a brief note in open_questions explaining why.

FEATURE_DESC: {{feature_desc}}
JARGON_JSON: {{jargon_json}}
EVIDENCE_JSON: {{evidence_json}}

Return ONLY JSON:
{
 "findings":[
   {"key_point":"...", "supports":"approve|reject|uncertain",
    "evidence":[{"kind":"doc|web","ref":"...","snippet":"..."}]
   }
 ],
 "open_questions":[
   {"text":"...","category":"policy|data|eng|product","blocking":true}
 ]
}
""".strip()

# ---------- UTILITIES ----------
def _dump_jargon_for_prompt(jargon: object) -> str:
    """
    Normalizes JargonQueryResult (Pydantic) or dict to a stable JSON string.
    """
    if jargon is None:
        return "{}"
    if hasattr(jargon, "model_dump"):
        return json.dumps(jargon.model_dump(), sort_keys=True)
    if isinstance(jargon, dict):
        return json.dumps(jargon, sort_keys=True)
    return "{}"

# def _tags_from(ctx: StateContext, payload: Optional[dict]) -> dict:
#     """
#     Tag derivation for Planner:
#     - Prefer tags derived from ctx.jargon_translation (populated by Jargon Agent).
#     - Fallback to payload['jargon_result'] when ctx is empty.
#     - Merge with regex-derived text tags from name/description.
#     """
#     jr = ctx.jargon_translation or (payload.get("jargon_result") if payload else None)
#     t1 = jargon_to_tags(jr)
#     name = ctx.feature_name or (payload.get("standardized_name") if payload else "")
#     desc = ctx.feature_description or (payload.get("standardized_description") if payload else "")
#     t2 = derive_text_tags(f"{name} {desc}")
#     return merge_tag_sets(t1, t2)

# ---------- AGENT FACTORIES ----------
def create_analysis_planner() -> Agent[StateContext]:
    """
    Stateless planner; returns AnalysisPlan(JSON).
    """
    return Agent[StateContext](
        name="Analysis Planner (Alvin)",
        instructions=plan_prompt,
        tools=[],                # no retrieval here
        output_type=AnalysisPlan,
        model="gpt-5-nano",
    )

def create_analysis_synthesizer() -> Agent[StateContext]:
    """
    Stateless synthesizer; returns AnalysisFindings(JSON).
    """
    return Agent[StateContext](
        name="Analysis Synthesizer (Alvin)",
        instructions=synth_prompt,
        tools=[],                # no retrieval here
        output_type=AnalysisFindings,
        model="gpt-5-nano",
    )

# ---------- HELPERS (legacy convenience) ----------
def prepare_from_feature_payload(payload: dict) -> tuple[str, dict, dict]:
    """
    Accept a StandardizedFeature-like payload and compute:
      - feature_text (desc fallback to name)
      - jargon_dict (payload["jargon_result"])
      - merged tags for the planner
    """
    name = payload.get("standardized_name") or ""
    desc = payload.get("standardized_description") or name
    jargon_dict = payload.get("jargon_result") or {}

    # tj = jargon_to_tags(jargon_dict)
    # tt = derive_text_tags(f"{name} {desc}")
    # tags = merge_tag_sets(tj, tt)

    def _sorted_dict(d: dict) -> dict:
        out = {}
        for k in sorted(d.keys()):
            v = d[k]
            out[k] = sorted(v) if isinstance(v, list) else v
        return out

    return desc, jargon_dict 

# ---------- RUN STEPS ----------
async def run_planner(planner: Agent[StateContext], feature_payload: Optional[dict], ctx: StateContext) -> AnalysisPlan:
    """
    Builds a deterministic planner prompt using StateContext (preferred) or fallback payload.
    Saves the result to ctx.analysis_plan for the Orchestrator to pass to Retrieval Agent.
    """
    feature_name = ctx.feature_name or (feature_payload or {}).get("standardized_name") or ""
    feature_desc = ctx.feature_description or (feature_payload or {}).get("standardized_description") or feature_name

    prompt = (plan_prompt(None, None)
              .replace("{{feature_name}}", feature_name)
              .replace("{{feature_desc}}", feature_desc)
              .replace("{{jargon_json}}", _dump_jargon_for_prompt(
                  ctx.jargon_translation or (feature_payload or {}).get("jargon_result")
              ))

             )

    res = await Runner.run(planner, prompt, context=ctx)
    ctx.analysis_plan = res.final_output
    # cache for downstream agents
    ctx.feature_name = feature_name
    ctx.feature_description = feature_desc
    return res.final_output

async def run_synthesizer(
    synth: Agent[StateContext],
    feature_payload: Optional[dict],
    evidence: List[Evidence],
    ctx: StateContext
) -> AnalysisFindings:
    """
    Builds a deterministic synth prompt with:
      - feature description
      - jargon JSON
      - EVIDENCE_JSON (verbatim list of Evidence)
    Returns AnalysisFindings and stores into ctx.analysis_findings.

    BLOCKING BEHAVIOR (IMPORTANT):
    - This agent does NOT enforce blocking; it only emits open_questions with blocking flags.
    - The Reviewer is responsible for interpreting blocking (penalties/HITL).
    """
    feature_desc = ctx.feature_description or (feature_payload or {}).get("standardized_description") or ""
    jr_json = _dump_jargon_for_prompt(ctx.jargon_translation or (feature_payload or {}).get("jargon_result"))
    evidence_json = json.dumps(
        [e.model_dump() if hasattr(e, "model_dump") else e for e in evidence],
        sort_keys=True
    )

    prompt = (synth_prompt(None, None)
              .replace("{{feature_desc}}", feature_desc)
              .replace("{{jargon_json}}", jr_json)
              .replace("{{evidence_json}}", evidence_json))

    res = await Runner.run(synth, prompt, context=ctx)
    ctx.analysis_findings = res.final_output
    return res.final_output

# ---------- Local demo ----------
if __name__ == "__main__":
    import asyncio
    from schemas.jargons import JargonQueryResult  # optional; used if populating ctx
    from schemas.analysis import Evidence

    # === SAMPLE INPUT (post Jargon Agent) ===
    # In the real flow, this StandardizedFeature comes from the Jargon Agent.
    SAMPLE = {
      "standardized_name": "Curfew-based login restriction for under-18 users in Utah",
      "standardized_description": "Enforce curfew for Utah minors via ASL + GH; EchoTrace audit; ShadowMode rollout.",
      "jargon_result": {
        "detected_terms": [
          {"term":"ASL","definition":"Age-sensitive logic"},
          {"term":"GH","definition":"Geo-handler"}
        ],
        "searched_terms": [
          {"term":"Utah Social Media Regulation Act","definition":"state social media law","sources":[{"title":"Utah OAG","link":"https://oag.utah.gov"}]}
        ],
        "unknown_terms":[]
      }
    }

    # === MOCK EVIDENCE (pretend this came from Retrieval Agent) ===
    # Each entry will be turned into one Finding by the synthesizer.
    MOCK_EVIDENCE = [
      {"kind":"doc","ref":"doc:utah_social_media_act#p12","snippet":"Utah law requires parental consent and allows curfew-style protections for minors."},
      {"kind":"doc","ref":"doc:utah_curfew_guidance#p3","snippet":"Curfew restrictions must be enforced via age verification and Utah targeting."},
      {"kind":"web","ref":"https://ftc.gov/child-privacy","snippet":"FTC guidance emphasizes parental consent and safeguards for minors."}
    ]

    # Toggle: simulate the real pipeline where ctx holds the Jargon Pydantic model
    USE_PYDANTIC_JARGON_IN_CTX = True

    async def _demo():
        # NOTE: In production, reaching this agent means PRE-SCREEN has ALREADY passed.
        ctx = StateContext(session_id="demo-utah-001", current_agent="analysis")

        if USE_PYDANTIC_JARGON_IN_CTX:
            ctx.feature_name = SAMPLE["standardized_name"]
            ctx.feature_description = SAMPLE["standardized_description"]
            ctx.jargon_translation = JargonQueryResult(**SAMPLE["jargon_result"])
            payload_for_planner = None  # rely on ctx.*
        else:
            payload_for_planner = SAMPLE  # fallback: planner/synth read from payload if ctx lacks data

        planner = create_analysis_planner()
        synth   = create_analysis_synthesizer()

        # ---- PLAN (for Retrieval Agent) ----
        plan = await run_planner(planner, payload_for_planner, ctx)
        print("=== ANALYSIS PLAN ===")
        for i, need in enumerate(plan.retrieval_needs, 1):
            print(f"{i}. query={need.query} | must={need.must_tags} | nice={need.nice_to_have_tags}")

        # ---- SYNTHESIZE (from evidence) ----
        findings = await run_synthesizer(synth, payload_for_planner, MOCK_EVIDENCE, ctx)
        print("\n=== ANALYSIS FINDINGS ===")
        for f in findings.findings:
            print(f"- [{f.supports}] {f.key_point}")
            for ev in f.evidence:
                print(f"   • {ev.kind}: {ev.ref}")

        if findings.open_questions:
            print("\nOpen Questions:")
            for q in findings.open_questions:
                # 'blocking=True' here tells the Reviewer/HITL to treat it as a hard gap.
                print(f" - ({q.category}, blocking={q.blocking}) {q.text}")

    asyncio.run(_demo())