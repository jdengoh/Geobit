"""
Summarizer Agent formats final output for clients.
Input: feature, jargon_result, analysis_plan, reviewer_decision, analysis_findings.
Output: concise dict with key sections.
"""

from typing import Any, Dict

from agents import Agent, RunContextWrapper

from .analysis_agent_alvin import StateContext


def summarizer_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return (
        "You are a deterministic Summarizer. Format the provided objects into a concise JSON with keys: "
        "feature, decision, highlights, open_questions. No extra prose."
    )


def create_summarizer_agent() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Summarizer Agent",
        instructions=summarizer_prompt,
        tools=[],
        output_type=dict,
        model="gpt-5-nano",
    )


def summarize(_: Agent[StateContext], payload: Dict[str, Any]) -> Dict[str, Any]:
    findings = payload.get("analysis_findings", {})
    open_questions = findings.get("open_questions") if isinstance(findings, dict) else []
    highlights = []
    if isinstance(findings, dict):
        for f in findings.get("findings", []):
            highlights.append(f.get("key_point"))
    return {
        "feature": payload.get("feature"),
        "decision": payload.get("reviewer_decision"),
        "highlights": highlights,
        "open_questions": open_questions or [],
    }


