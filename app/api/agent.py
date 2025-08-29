import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

from app.core.dependencies import get_agent_service
from app.schemas.agent import AgentRequest
from app.services.agent_service import AgentService


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


# @router.get("/pipeline", summary="Run Pipeline (without params)")
# async def run_pipeline_demo(svc: AgentService = Depends(get_agent_service)):
#     return await svc.run_deterministic_pipeline(
#         feature_name="Demo Feature",
#         feature_description="Demo description",
#         session_id="api-pipeline-demo",
#     )

@router.get("/pipeline", summary="Run Pipeline (with params)")
async def run_pipeline_q(
    feature: str,
    description: str,
    svc: AgentService = Depends(get_agent_service),
):
    return await svc.run_deterministic_pipeline(
        feature_name=feature,
        feature_description=description,
        session_id="api-pipeline",
    )


# @router.post("/pipeline", summary="Run Pipeline (without params)")
# async def run_pipeline_endpoint(request: AgentRequest, svc: AgentService = Depends(get_agent_service)):
#     return await svc.run_deterministic_pipeline(
#         feature_name=request.title,
#         feature_description=request.description,
#         session_id="api-pipeline",
#     )


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
