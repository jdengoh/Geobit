"""
Reviewer Agent applies deterministic HITL gating rules on AnalysisFindings.

Rules (example):
- If any finding has supports == 'uncertain' OR there are open_questions → require human review.
- Else auto-approve.
"""

from agents import Agent, RunContextWrapper

from .analysis_agent_alvin import StateContext, AnalysisFindings


def reviewer_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return (
        "You are a deterministic Reviewer. Examine the provided findings and open_questions. "
        "Return JSON: { \"decision\": \"auto_approve|human_review\", \"reason\": \"...\" }."
    )


def create_reviewer_agent() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Reviewer Agent",
        instructions=reviewer_prompt,
        tools=[],
        output_type=dict,
        model="gpt-5-nano",
    )


def review_findings(_: Agent[StateContext], findings: AnalysisFindings) -> dict:
    needs_hitl = bool(findings.open_questions)
    for f in findings.findings:
        if getattr(f, "supports", "uncertain") == "uncertain":
            needs_hitl = True
            break
    if needs_hitl:
        return {"decision": "human_review", "reason": "Uncertain findings or open questions present."}
    return {"decision": "auto_approve", "reason": "All findings definitive; no open questions."}


