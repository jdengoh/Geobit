"""
Retrieval Agent (deterministic stub).

- Accepts AnalysisPlan.retrieval_needs and returns a stable list of Evidence.
- Replace the body of retrieve_evidence() with real KB/Web calls later.
"""

from typing import List

from agents import Agent, RunContextWrapper

from .analysis_agent_alvin import StateContext, Evidence, AnalysisPlan


def retrieval_agent_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return (
        "You are a deterministic Retrieval Agent. You will receive a list of retrieval needs "
        "(queries + tags). You MUST return a JSON list of Evidence objects with fields: "
        "kind ('doc' or 'web'), ref (string), snippet (string). Keep order stable."
    )


def create_retrieval_agent() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Retrieval Agent",
        instructions=retrieval_agent_prompt,
        tools=[],
        output_type=List[Evidence],
        model="gpt-5-nano",
    )


async def retrieve_evidence(_: Agent[StateContext], plan: AnalysisPlan, __: StateContext) -> List[Evidence]:
    """Deterministic placeholder implementation.

    For each RetrievalNeed, emit a simple web Evidence with the query echoed as snippet.
    """
    evidence: List[Evidence] = []
    for need in plan.retrieval_needs:
        evidence.append(
            Evidence(
                kind="web",
                ref=f"search://{need.query[:60].replace(' ', '+')}",
                snippet=need.query,
            )
        )
    return evidence


