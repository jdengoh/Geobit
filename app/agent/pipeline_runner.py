"""
Deterministic outer-loop pipeline (no orchestrator agent).

Order:
1) Jargon Agent (may invoke Web Search Agent as its tool)
2) Analysis Planner
3) Retrieval (stubbed here; plug your KB/Web retriever)
4) Analysis Synthesizer

Inputs: feature name/description
Output: combined dictionary with jargon JSON, plan, findings
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from agents import Agent, Runner

# Load .env from repo root deterministically
try:
    from dotenv import load_dotenv
    _ROOT = Path(__file__).resolve().parents[2]
    _ENV = _ROOT / ".env"
    if _ENV.exists():
        load_dotenv(_ENV)
except Exception:
    pass

# Local imports
from jargen_agent import create_jargon_agent
from analysis_agent_alvin import (
    StateContext,
    Evidence,
    AnalysisPlan,
    AnalysisFindings,
    create_analysis_planner,
    create_analysis_synthesizer,
    run_planner,
    run_synthesizer,
)


async def _run_jargon_agent(
    agent: Agent[StateContext],
    ctx: StateContext,
    *,
    feature_name: str,
    feature_description: str,
) -> Dict[str, Any]:
    """Run jargon agent to produce StandardizedFeature JSON."""
    prompt = (
        "You are given a feature artifact. Extract terms and follow instructions.\n"
        f"FEATURE_NAME: {feature_name}\n"
        f"FEATURE_DESC: {feature_description}\n"
        "Return ONLY the StandardizedFeature JSON."
    )
    res = await Runner.run(agent, prompt, context=ctx)
    # The agent's output_type is a Pydantic model; convert to plain dict
    output = res.final_output
    return output.model_dump() if hasattr(output, "model_dump") else output


async def _retrieve_evidence_stub(plan: AnalysisPlan) -> List[Evidence]:
    """Deterministic placeholder for retrieval step.

    Replace this with your KB/Web retriever that uses plan.retrieval_needs.
    Keep order stable for determinism.
    """
    _ = plan  # unused in stub
    return []


async def run_pipeline(
    feature_name: str,
    feature_description: str,
    session_id: str = "session-001",
) -> Dict[str, Any]:
    """Run the deterministic pipeline and return a combined result payload."""
    ctx = StateContext(session_id=session_id, current_agent="pipeline")

    # 1) Jargon Agent (includes Web Search Agent as tool)
    jargon_agent = create_jargon_agent()
    jargon_json = await _run_jargon_agent(
        jargon_agent, ctx, feature_name=feature_name, feature_description=feature_description
    )

    # 2) Analysis Planner
    planner = create_analysis_planner()
    feature_payload = {
        "standardized_name": feature_name,
        "standardized_description": feature_description,
        "jargon_result": jargon_json,
    }
    plan = await run_planner(planner, feature_payload, ctx)

    # 3) Retrieval (stub here)
    evidence = await _retrieve_evidence_stub(plan)

    # 4) Analysis Synthesizer
    synth = create_analysis_synthesizer()
    findings = await run_synthesizer(synth, feature_payload, evidence, ctx)

    # Assemble deterministic output
    result = {
        "feature": {
            "name": feature_name,
            "description": feature_description,
        },
        "jargon_result": jargon_json,
        "analysis_plan": plan.model_dump() if hasattr(plan, "model_dump") else plan,
        "retrieved_evidence": [
            e.model_dump() if hasattr(e, "model_dump") else e for e in evidence
        ],
        "analysis_findings": findings.model_dump() if hasattr(findings, "model_dump") else findings,
    }
    return result


async def _demo() -> None:
    feature_name = "Curfew-based login restriction for under-18 users in Utah"
    feature_description = (
        "Implements a curfew-based login restriction for users under 18 in Utah. "
        "Uses Age Screening Logic (ASL) to detect minor accounts and a Geo Handler (GH) "
        "to enforce restrictions only within Utah boundaries. The feature activates during "
        "restricted night hours and logs activity with EchoTrace for auditability. "
        "ShadowMode is used during the initial rollout to avoid user-facing alerts while collecting analytics."
    )

    result = await run_pipeline(feature_name, feature_description, session_id="demo-pipeline-001")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(_demo())


