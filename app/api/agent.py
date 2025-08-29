import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

from app.core.dependencies import get_agent_service
from app.schemas.agent import AgentRequest
from app.services.agent_service import AgentService
from app.agent.schemas.stream import StreamEvent, FEEnvelope, FEUI
from app.agent.schemas.agents import StateContext
from app.agent.summariser_agent import run_summariser


def _jsonl(d: dict) -> bytes:
    return (json.dumps(d) + "\n").encode("utf-8")

@router.get("/agents", summary="List Agents")
async def list_agents():
    """List all available agents and their configurations."""

    agent_service = AgentService()
    agents = agent_service.get_agent()

    return {
        name: {
            "instructions": agent.instructions,
            "model": agent.model,
            "response_model": agent.output_type.__name__ if agent.output_type else None,
            "handoffs": [handoff.name for handoff in agent.handoffs],
        }
        for name, agent in agents.items()
    }


@router.post("/analyze", summary="Analyze Feature for Geo-Compliance Requirements")
async def analyze_feature_compliance(
    request: AgentRequest, agent_service: AgentService = Depends(get_agent_service)
):
    logger.info(f"Received compliance analysis request: {request}")

    feature_text = f"Title: {request.title}\nDescription: {request.description}"

    async def response_generator() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in agent_service.run_streaming_workflow(
                user_input=feature_text,
                history=request.history,
                current_agent="jargon_agent",
            ):
                yield chunk.model_dump_json() + "\n"
        except Exception as exc:
            error_response = {
                "agent_name": "triage_agent",
                "event_type": "ERROR",
                "data": {"type": exc.__class__.__name__, "message": str(exc)},
            }
            yield json.dumps(error_response) + "\n"

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")


#-------------------------------Alvin's Code-----------------------------------#
@router.post("/analyze/stream")
async def analyze_stream(payload: dict):
    async def gen():
        ctx = StateContext(session_id=f"sess-{int(time.time())}", current_agent="orchestrator")
        # (A) emit progress if you like
        yield _jsonl(StreamEvent(event="stage", stage="pre_scan", message="Pre-scan starting").model_dump())
        # run pre-scan later; for now just keep streaming demo statuses:
        yield _jsonl(StreamEvent(event="stage", stage="jargon", message="Jargon expanding").model_dump())
        yield _jsonl(StreamEvent(event="stage", stage="analysis", message="Planning + synthesis").model_dump())
        yield _jsonl(StreamEvent(event="stage", stage="review", message="Reviewer scoring").model_dump())

        # (B) Build the FE envelope using your summariser (this consumes reviewer output in ctx)
        fe: FEEnvelope = await run_summariser(ctx)  # you already have DecisionRecord in ctx

        # (C) FINAL event — frontend only cares about this for now
        yield _jsonl(StreamEvent(event="final", stage="summarise", payload=fe.model_dump(), terminating=True).model_dump())

    return StreamingResponse(gen(), media_type="application/x-ndjson")
#-------------------------------Alvin's Code-----------------------------------#
# TODO: non-streaming
# @router.post("/analyze", summary="Analyze Feature for Geo-Compliance Requirements")
# async def analyze_feature_compliance(
#     request: AgentRequest,
#     agent_service: AgentService = Depends(get_agent_service)
# ):
#     logger.info(f"Received compliance analysis request: {request}")

#     # Format as user message
#     feature_text = f"Title: {request.title}\nDescription: {request.description}"

#     response = await agent_service.run_workflow(
#         user_input=feature_text,
#         history=request.history,
#         current_agent="classifier_agent",
#     )

#     return response
