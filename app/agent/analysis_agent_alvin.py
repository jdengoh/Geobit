"""
Analysis Agent (Planner + Synthesizer)

Big picture:
  Feature Artifact + Jargon JSON
        │
        ▼
   [Planner Agent]  --(AnalysisPlan.retrieval_needs)-->  Retrieval Agent
                                                           │
                                                           ▼
                                               (Evidence[]: doc/web+snippets)
                                                           │
                                                           ▼
   [Synthesizer Agent] --(AnalysisFindings: findings+open_questions)--> next stage

Key design choices:
- Planner and Synthesizer are *stateless specialists*. They do not fetch sources.
- Output is *strict JSON* validated by Pydantic -> reliable, auditable.
- Orchestrator glues components; Retrieval Agent handles KB/Web; Reviewer/HITL sits after Synthesizer.
"""
from agents import Agent, Runner, RunContextWrapper, ModelSettings
from typing import List, Optional
import json
from pydantic import BaseModel
from schemas.agent import StateContext
from _tagging import jargon_to_tags, derive_text_tags, merge_tag_sets
from schemas.analysis import RetrievalNeed, Evidence, Finding, OpenQuestion, AnalysisPlan, AnalysisFindings

"""
Schemas used by the Analysis Agent.

Flow overview:
1) Planner outputs AnalysisPlan.retrieval_needs -> sent to Retrieval Agent.
2) Retrieval Agent returns a list of Evidence -> fed into Synthesizer.
3) Synthesizer outputs AnalysisFindings -> used by downstream Report/Reviewer.
"""



# -------------------- Runtime state (light; persisted elsewhere) --------------------
# class StateContext(BaseModel):
#     session_id: str
#     current_agent: str
#     feature_name: Optional[str] = None
#     feature_description: Optional[str] = None
#     jargon_translation: Optional[dict] = None
#     analysis_plan: Optional[AnalysisPlan] = None
#     retrieved_evidence: List[Evidence] = []
#     analysis_findings: Optional[AnalysisFindings] = None

# -------------------- Prompts --------------------
def plan_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
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
    return """
You are a Compliance Analysis Synthesizer.

FEATURE_DESC: {{feature_desc}}
JARGON_JSON: {{jargon_json}}
EVIDENCE_JSON: {{evidence_json}}

Produce JSON:
{
 "findings":[
   {"key_point":"...", "supports":"approve|reject|uncertain",
    "evidence":[{"kind":"doc|web","ref":"...","snippet":"..."}]
   }
 ],
 "open_questions":[
   "..."  // include any missing pieces that block a decision
 ]
}
Rules:
- USE EVERY evidence item if relevant; if an item is irrelevant, mention why in open_questions.
- No extra text; JSON only.
""".strip()


# -------------------- Agents --------------------
def create_analysis_planner() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Analysis Planner (Alvin)",
        instructions=plan_prompt,
        tools=[],
        output_type=AnalysisPlan,
        model="gpt-5-nano",
    )

def create_analysis_synthesizer() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Analysis Synthesizer (Alvin)",
        instructions=synth_prompt,
        tools=[],
        output_type=AnalysisFindings,
        model="gpt-5-nano",
    )
# -------------------- Helpers --------------------
def prepare_from_feature_payload(payload: dict) -> tuple[str, dict, dict]:
    """
    Accept new JSON and return:
      - feature_text (use standardized_description; fallback to name)
      - jargon_dict (payload["jargon_result"])
      - merged tags (jargon_to_tags + derive_text_tags)
    """
    name = payload.get("standardized_name") or ""
    desc = payload.get("standardized_description") or name
    jargon_dict = payload.get("jargon_result") or {}

    tj = jargon_to_tags(jargon_dict)
    tt = derive_text_tags(f"{name} {desc}")
    tags = merge_tag_sets(tj, tt)

    # Keep JSON deterministic for the LLM
    def _sorted_dict(d: dict) -> dict:
        # sort lists, keep keys stable
        out = {}
        for k in sorted(d.keys()):
            v = d[k]
            if isinstance(v, list):
                out[k] = sorted(v)
            else:
                out[k] = v
        return out

    return desc, jargon_dict, _sorted_dict(tags)

async def run_planner(planner: Agent[StateContext], feature_payload: dict, ctx: StateContext) -> AnalysisPlan:
    feature_desc, jargon_dict, tags = prepare_from_feature_payload(feature_payload)
    ctx.feature_name = feature_payload.get("standardized_name")
    ctx.feature_description = feature_desc
    ctx.jargon_translation = jargon_dict

    prompt = (plan_prompt(None, None)
        .replace("{{feature_name}}", ctx.feature_name or "")
        .replace("{{feature_desc}}", feature_desc)
        .replace("{{jargon_json}}", json.dumps(jargon_dict, sort_keys=True))
        .replace("{{tags_json}}", json.dumps(tags, sort_keys=True)))

    res = await Runner.run(planner, prompt, context=ctx)
    ctx.analysis_plan = res.final_output
    return res.final_output

async def run_synthesizer(synth: Agent[StateContext], feature_payload: dict, evidence: List[Evidence], ctx: StateContext) -> AnalysisFindings:
    feature_desc = ctx.feature_description or feature_payload.get("standardized_description") or ""
    jargon_dict = ctx.jargon_translation or feature_payload.get("jargon_result") or {}

    evidence_json = json.dumps([e.model_dump() if hasattr(e, "model_dump") else e for e in evidence], sort_keys=True)

    prompt = (synth_prompt(None, None)
        .replace("{{feature_desc}}", feature_desc)
        .replace("{{jargon_json}}", json.dumps(jargon_dict, sort_keys=True))
        .replace("{{evidence_json}}", evidence_json))

    res = await Runner.run(synth, prompt, context=ctx)
    ctx.analysis_findings = res.final_output
    return res.final_output

# -------------------- Local demo --------------------
if __name__ == "__main__":
    import asyncio

    SAMPLE = {
      "standardized_name": "Curfew-based login restriction for under-18 users in Utah",
      "standardized_description": "Implements a curfew-based login restriction for users under 18 in Utah. Uses Age Screening Logic (ASL) to detect minor accounts and a Geo Handler (GH) to enforce restrictions only within Utah boundaries. The feature activates during restricted night hours and logs activity with EchoTrace for auditability. ShadowMode is used during the initial rollout to avoid user-facing alerts while collecting analytics.",
      "jargon_result": {
        "detected_terms": [
          {"term": "ASL", "definition": "Age-sensitive logic"},
          {"term": "GH", "definition": "Geo-handler; a module responsible for routing features based on user region"},
          {"term": "EchoTrace", "definition": "Log tracing mode to verify compliance routing"},
          {"term": "ShadowMode", "definition": "Deploy feature in non-user-impact way to collect analytics only"}
        ],
        "searched_terms": [
          {"term": "Utah Social Media Regulation Act", "definition": "…", "sources":[{"title": None, "link": None}]}
        ],
        "unknown_terms": []
      }
    }

    # Until Retrieval Agent is wired, mock stable evidence (keep order fixed)
    MOCK_EVIDENCE = [
        Evidence(kind="doc", ref="doc:utah_social_media_act#p12",
                snippet="Utah Social Media Regulation Act requires parental consent and protections for minors, effective Mar 1, 2024."),
        Evidence(kind="doc", ref="doc:utah_curfew_guidance#p3",
                snippet="Curfew-based restrictions for minors must be enforced by age verification and jurisdictional targeting in Utah."),
        Evidence(kind="web", ref="https://ftc.gov/child-privacy",
                snippet="FTC guidance emphasizes parental consent, age verification, data minimization for personalized or restricted experiences."),
    ]

    async def _demo():
        ctx = StateContext(session_id="demo-utah-001", current_agent="analysis")
        planner = create_analysis_planner()
        synth   = create_analysis_synthesizer()

        plan = await run_planner(planner, SAMPLE, ctx)
        print("=== ANALYSIS PLAN ===")
        for i, need in enumerate(plan.retrieval_needs, 1):
            print(f"{i}. query={need.query} | must={need.must_tags} | nice={need.nice_to_have_tags}")

        findings = await run_synthesizer(synth, SAMPLE, MOCK_EVIDENCE, ctx)
        print("\n=== ANALYSIS FINDINGS ===")
        for f in findings.findings:
            print(f"- [{f.supports}] {f.key_point}")
            for ev in f.evidence:
                print(f"   • {ev.kind}: {ev.ref}")
        if findings.open_questions:
            print("\nOpen Questions:")
            for q in findings.open_questions:
                print(" -", q)

    asyncio.run(_demo())