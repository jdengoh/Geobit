import asyncio
import json
import logging
import time
from typing import AsyncGenerator, List

from app.agent.analysis_agent import run_planner
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

from app.core.dependencies import get_agent_service
from app.schemas.agent import AgentRequest, AgentStreamResponse
from app.services.agent_service import AgentService
from app.agent.schemas.stream import StreamEvent, FEEnvelope, FEUI
from app.agent.schemas.agents import StateContext
from app.agent.schemas.pre_screen_result import PreScreenResult
from app.agent.schemas.analysis import AnalysisFindings, AnalysisPlan, Evidence,Finding,OpenQuestion
from app.agent.pre_screen_agent import create_llm_prescreener, run_prescreening
from app.agent.analysis_agent import (
    StateContext as AnalysisStateContext,
    Evidence,
    AnalysisPlan,
    AnalysisFindings,
    create_analysis_planner,
    create_analysis_synthesizer,
    run_planner,
    run_synthesizer,
)
from app.agent.retriever_agent import create_retrieval_agent, run_retrieval_agent
from app.agent.summariser_agent import run_summariser
from app.agent.review_agent import run_reviewer
from app.agent.jargen_agent import create_jargon_agent  
from agents import Runner, RunContextWrapper, trace


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


@router.post("/analyze", summary="Analyze Feature for Geo-Compliance Requirements ")
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


#-------------------------------Zuyuan's Code-----------------------------------#
# @router.post("/analyze/stream")
# async def analyze_stream(request: AgentRequest, demo: bool = True):
#     """
#     NDJSON streaming endpoint.
#     - Swagger will show 'can't parse JSON' (expected for streams).
#     - Use curl to see lines; FE reads until {"event":"final", ...}.
#     """
#     current_agent = getattr(request, "current_agent", None)  # or request.current_agent if it exists
#     if not current_agent:
#         current_agent = "jargon_agent"  # starting agent

#     feature_id = request.feature_id or f"feat-{int(time.time())}"

#     logger.info(f"Starting analysis stream for feature_id: {feature_id} with agent: {current_agent}")


#     async def gen():
#         ctx = StateContext(feature_id=feature_id, current_agent=current_agent)
#         ctx.feature_name = request.feature_name or "Untitled Feature"
#         ctx.feature_description = request.feature_description or ""

#         logger.info(f"Context initialized: {ctx}")



#         # Stage markers (nice for FE progress UI)
#         # **Pre-screen Agent**
#         yield _jsonl({"event":"stage","stage":"pre_scan","message":"⚡ Quick pre-checks…","terminating":False})
#         pre_screen_agent = create_llm_prescreener()
#         pre_screen: PreScreenResult = await run_prescreening(ctx)

#         # **Jargon Agent**
#         yield _jsonl({"event":"stage","stage":"jargon","message":"🔎 Expanding & normalising jargon…","terminating":False})
#         jargon_agent = create_jargon_agent()
#         prompt = (
#             "You are given a feature artifact. Extract terms and follow instructions.\n"
#             f"FEATURE_NAME: {ctx.feature_name}\nFEATURE_DESC: {ctx.feature_description}\n"
#             "Return ONLY the StandardizedFeature JSON."
#         )
#         res = await Runner.run(jargon_agent, prompt, context=RunContextWrapper(context=ctx))
#         ctx.jargon_translation = res.final_output.model_dump() if hasattr(res.final_output, "model_dump") else res.final_output

#         # **Analyzer**
#         yield _jsonl({"event":"stage","stage":"analysis-planning","message":"📝 Planning evidence & checks…","terminating":False})
#         feature_payload = {
#             "standardized_name": ctx.feature_name,
#             "standardized_description": ctx.feature_description,
#             "jargon_result": ctx.jargon_translation
#         }
#         analysis_planner = create_analysis_planner()
#         plan: AnalysisPlan = await run_planner(analysis_planner, feature_payload, ctx)

#         # **Retrieval**
#         yield _jsonl({"event":"stage","stage":"analysis-retrieval","message":"📚 Retrieving laws & sources…","terminating":False})
#         retriever_agent = create_retrieval_agent()
#         evidence: List[Evidence] = await run_retrieval_agent(retriever_agent, plan.retrieval_needs, ctx)

#         # **Synthesizer**
#         yield _jsonl({"event":"stage","stage":"analysis-synthesis","message":"🧩 Synthesising findings…","terminating":False})
#         analysis_synth = create_analysis_synthesizer()
#         findings: AnalysisFindings = await run_synthesizer(analysis_synth, feature_payload, evidence, ctx)

#         # **Reviewer**
#         yield _jsonl({"event":"stage","stage":"review","message":"✅ Reviewing & scoring decision…","terminating":False})
#         decision = await run_reviewer(ctx)      # fills ctx.decision_record

#         # **Summariser**
#         yield _jsonl({"event":"stage","stage":"summarise","message":"📦 Finalising results…","terminating":False})
#         fe = await run_summariser(ctx)          # reads ctx.decision_record + ctx.feature_*

#         # FINAL payload (FE listens for this)
#         yield _jsonl({"event":"final","stage":"final","payload":fe.model_dump(), "terminating":True})

#     return StreamingResponse(gen(), media_type="application/x-ndjson")



@router.post("/analyze/stream", summary="Analyze Feature for Geo-Compliance Requirements")
async def analyze_stream(
    request: AgentRequest, 
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    NDJSON streaming endpoint for feature compliance analysis.
    """
    current_agent = getattr(request, "current_agent", None) or "jargon_agent"
    feature_id = getattr(request, "feature_id", None) or f"feat-{int(time.time())}"
    
    logger.info(f"Starting analysis stream for feature_id: {feature_id} with agent: {current_agent}")

    # Create and configure StateContext
    ctx = StateContext(feature_id=feature_id, current_agent=current_agent)
    ctx.feature_name = request.feature_name or "Untitled Feature"
    ctx.feature_description = request.feature_description or ""

    logger.info(f"Context initialized: {ctx}")

    async def response_generator() -> AsyncGenerator[bytes, None]:
        try:
            with trace("agent_service.run_full_workflow"):
                async for chunk in agent_service.run_full_workflow(ctx):
                    logger.info(f"Yielding chunk: {chunk}")
                    yield chunk.model_dump_json().encode() + b"\n"
        except Exception as exc:
            error_response = AgentStreamResponse(
                agent_name="error_handler",
                event="ERROR",
                data={"type": exc.__class__.__name__, "message": str(exc)}
            )
            yield error_response.model_dump_json().encode() + b"\n"

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")



#-------------------------------Zuyuan's Code-----------------------------------#

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
