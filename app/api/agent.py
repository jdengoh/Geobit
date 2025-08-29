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
from app.agent.schemas.analysis import AnalysisFindings, AnalysisPlan, Evidence,Finding,OpenQuestion
from app.agent.summariser_agent import run_summariser
from app.agent.review_agent import run_reviewer
from app.repo.fe_repo import insert_fe_envelope


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
async def analyze_stream(payload: dict, demo: bool = True):
    """
    NDJSON streaming endpoint.
    - Swagger will show 'can't parse JSON' (expected for streams).
    - Use curl to see lines; FE reads until {"event":"final", ...}.
    """
    async def gen():
        ctx = StateContext(session_id=f"sess-{int(time.time())}", current_agent="orchestrator")
        ctx.feature_name = payload.get("standardized_name") or "Untitled Feature"
        ctx.feature_description = payload.get("standardized_description") or ""

        # Stage markers (nice for FE progress UI)
        
        yield _jsonl({"event":"stage","stage":"jargon","message":"Jargon expanding","terminating":False})
        yield _jsonl({"event":"stage","stage":"pre_scan","message":"Pre-scan starting","terminating":False})
        yield _jsonl({"event":"stage","stage":"analysis","message":"Planning + synthesis","terminating":False})

        # ---- DEMO PIPELINE (until retrieval is wired) ----
        # Build a trivial AnalysisFindings to drive reviewer + summariser.
        # You can branch based on text to get different outcomes quickly.
        desc = (ctx.feature_description or "").lower()
        if "utah" in desc and ("curfew" in desc or "minor" in desc):
            # YES: evidence suggests geo compliance is required
            af = AnalysisFindings(
                findings=[
                    Finding(
                        key_point="Utah law requires parental consent and allows curfew-style protections for minors.",
                        supports="approve",
                        evidence=[Evidence(kind="doc", ref="doc:utah_social_media_act#p12", snippet="...")]
                    ),
                    Finding(
                        key_point="Curfew must be enforced via age verification and Utah targeting.",
                        supports="approve",
                        evidence=[Evidence(kind="doc", ref="doc:utah_curfew_guidance#p3", snippet="...")]
                    ),
                ],
                open_questions=[]
            )
        elif "market testing" in desc or "a/b" in desc or "experiment" in desc:
            # NO: looks like business rollout, not legal requirement
            af = AnalysisFindings(
                findings=[
                    Finding(
                        key_point="Geofencing for experimentation is business-driven; no law cited.",
                        supports="reject",
                        evidence=[]
                    )
                ],
                open_questions=[]
            )
        else:
            # UNCLEAR: needs review
            af = AnalysisFindings(
                findings=[
                    Finding(
                        key_point="No explicit law or regulator cited; intent unclear.",
                        supports="uncertain",
                        evidence=[]
                    )
                ],
                open_questions=[OpenQuestion(text="Clarify whether this is due to legal/regulatory requirement.", category="policy", blocking=False)]
            )

        # Put findings into context for reviewer/summariser
        ctx.analysis_findings = af

        yield _jsonl({"event":"stage","stage":"review","message":"Reviewer scoring","terminating":False})
        decision = await run_reviewer(ctx)      # fills ctx.decision_record

        yield _jsonl({"event":"stage","stage":"summarise","message":"Formatting final UI payload","terminating":False})
        fe = await run_summariser(ctx)          # reads ctx.decision_record + ctx.feature_*
        # 🔐 persist and echo IDs back to FE
        try:
            db_id = await insert_fe_envelope(fe.model_dump(), ctx.session_id)
            # print("fe type:", type(fe))
            # print("fe module:", fe.__class__.__module__)
            # print("fe fields:", list(fe.model_fields.keys()))
            fe = fe.model_copy(update={
                    "session_id": ctx.session_id,
                    "db_id": db_id,
                })
        except Exception:
            logger.exception("Failed to save FEEnvelope")


        # FINAL payload (FE listens for this)
        yield _jsonl({"event":"final","stage":"summarise","payload":fe.model_dump(), "terminating":True})

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
