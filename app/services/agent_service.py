import json
import logging
from enum import StrEnum
from typing import Any, AsyncGenerator, List, Optional

from agents import (
    AgentUpdatedStreamEvent,
    MessageOutputItem,
    RawResponsesStreamEvent,
    RunContextWrapper,
    RunItemStreamEvent,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
    TResponseInputItem,
    trace,
)

# from app.agents.triage import create_triage_agent
from openai.types.responses import ResponseContentPartDoneEvent, ResponseTextDeltaEvent
from pydantic import BaseModel

from app.agent.pre_screen_agent import create_llm_prescreener, run_prescreening
from app.agent.analysis_agent import create_analysis_planner, create_analysis_synthesizer
from app.agent.jargen_agent import create_jargon_agent
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
from app.agent.review_agent import create_llm_reviewer, run_reviewer
from app.agent.schemas.agents import StateContext
from app.agent.schemas.pre_screen_result import PreScreenResult
from app.agent.summariser_agent import run_summariser
from app.schemas.agent import AgentStreamResponse


logger = logging.getLogger(__name__)


class EventType(StrEnum):
    DELTA_TEXT_EVENT = "delta_text_event"
    COMPLETED_TEXT_EVENT = "completed_text_event"
    NEW_AGENT_EVENT = "new_agent_event"
    TOOL_CALL_EVENT = "tool_call_event"
    TOOL_CALL_OUTPUT_EVENT = "tool_call_output_event"
    TERMINATING_EVENT = "terminating_event"
    ERROR_EVENT = "error_event"


# class StateContext(BaseModel):
#     """Context object for carrying state through the pipeline"""

#     session_id: str
#     current_agent: str
#     jargon_translation: Optional[dict] = None
#     sources: Optional[List[str]] = None


class AgentResponse(BaseModel):
    """Pydantic model for agent response structure"""

    event_type: EventType
    agent_name: str
    history: Optional[
        List[Any]
    ]  # You might want to create a more specific type for history items
    message: Optional[str] = None
    data_type: Optional[str] = None
    data: Optional[Any] = (
        None  # Could be dict, str, or other types depending on use case
    )


class RunContext:
    def __init__(self, current_agent: str | None = None, restart: bool = False):
        self.current_agent = current_agent
        self.restart = restart
        # self.data_type = data_type  # used to indicate the type of data being handled (e.g. "user_profile_data")


class AgentService:

    def __init__(self):
        self.pre_screen_agent = create_llm_prescreener()
        self.jargon_agent = create_jargon_agent()
        # analysis stack
        self.analysis_planner = create_analysis_planner()
        self.analysis_synth = create_analysis_synthesizer()
        self.retriever_agent = create_retrieval_agent()
        self.review_agent = create_llm_reviewer()


        # self.current_agent_mapping = {
        #     # "triage_agent": self.triage_agent,
        #     "jargon_agent": self.jargon_agent,
        #     # "analysis_planner_agent": self.analysis_planner_agent,
        #     # "analysis_synthesizer_agent": self.analysis_synthesizer_agent,
        # }


    def get_agent(self):
        """
        Return all available agents in the system.
        """
        agents = {
            # TODO: no triage for now
            "Pre-Screen Agent": self.pre_screen_agent,
            "Jargon Agent": self.jargon_agent,
            "Analysis Planner": self.analysis_planner,
            "Analysis Synthesizer": self.analysis_synth,
            "Retriever Agent": self.retriever_agent,
            "Reviewer Agent": self.review_agent
        }
        return agents

    async def run_full_workflow(
        self,
        ctx: StateContext,
    ) -> AsyncGenerator[AgentStreamResponse, None]:
        """
        Main workflow (streaming) to run the full compliance analysis pipeline.
        Takes a pre-configured StateContext.
        """
        
        logger.info(f"Starting analysis workflow for feature_id: {ctx.feature_id} with agent: {ctx.current_agent}")

        try:
            
            logger.info("Step 1: Pre-screening")
            # Stage 1: Pre-screen Agent
            yield AgentStreamResponse(
                agent_name="pre_screen_agent",
                event="stage",
                stage="pre_scan",
                message="⚡ Quick pre-checks…",
                terminating=False
            )
            pre_screen: PreScreenResult = await run_prescreening(ctx)

            logger.info("Step 2: Jargon Agent")
            # Stage 2: Jargon Agent
            yield AgentStreamResponse(
                agent_name="jargon_agent",
                event="stage",
                stage="jargon",
                message="🔎 Expanding & normalising jargon…",
                terminating=False
            )
            prompt = (
                "You are given a feature artifact. Extract terms and follow instructions.\n"
                f"FEATURE_NAME: {ctx.feature_name}\nFEATURE_DESC: {ctx.feature_description}\n"
                "Return ONLY the StandardizedFeature JSON."
            )
            res = await Runner.run(self.jargon_agent, prompt, context=RunContextWrapper(context=ctx))
            ctx.jargon_translation = res.final_output.model_dump() if hasattr(res.final_output, "model_dump") else res.final_output

            logger.info("Step 3: Analysis Planning")
            # Stage 3: Analysis Planning
            yield AgentStreamResponse(
                agent_name="analysis_planner",
                event="stage",
                stage="analysis-planning",
                message="📝 Planning evidence & checks…",
                terminating=False
            )
            feature_payload = {
                "standardized_name": ctx.feature_name,
                "standardized_description": ctx.feature_description,
                "jargon_result": ctx.jargon_translation
            }
            plan: AnalysisPlan = await run_planner(self.analysis_planner, feature_payload, ctx)

            logger.info("Step 4: Evidence Retrieval")
            # Stage 4: Retrieval
            yield AgentStreamResponse(
                agent_name="retriever_agent",
                event="stage",
                stage="analysis-retrieval",
                message="📚 Retrieving laws & sources…",
                terminating=False
            )
            evidence: List[Evidence] = await run_retrieval_agent(self.retriever_agent, plan.retrieval_needs, ctx)

            logger.info("Step 5: Analysis Synthesis")
            # Stage 5: Synthesis
            yield AgentStreamResponse(
                agent_name="analysis_synthesizer",
                event="stage",
                stage="analysis-synthesis",
                message="🧩 Synthesising findings…",
                terminating=False
            )
            findings: AnalysisFindings = await run_synthesizer(self.analysis_synth, feature_payload, evidence, ctx)

            logger.info("Step 6: Review")
            # Stage 6: Review
            yield AgentStreamResponse(
                agent_name="review_agent",
                event="stage",
                stage="review",
                message="✅ Reviewing & scoring decision…",
                terminating=False
            )
            decision = await run_reviewer(ctx)

            logger.info("Step 7: Summarisation")
            # Stage 7: Summary
            yield AgentStreamResponse(
                agent_name="summarizer_agent",
                event="stage",
                stage="summarise",
                message="📦 Finalising results…",
                terminating=False
            )
            fe = await run_summariser(ctx)

            # Final result
            yield AgentStreamResponse(
                agent_name="final",
                event="final",
                payload=fe.model_dump(),
                terminating=True
            )
            logger.info("Analysis workflow completed successfully.")

        except Exception as exc:
            logger.error(f"Workflow error: {exc}", exc_info=True)
            yield AgentStreamResponse(
                agent_name="error_handler",
                event="error",
                payload={"type": exc.__class__.__name__, "message": str(exc)},
                terminating=True
            )


    # TODO: more detailed streaming workflow if required in the future :D
    
    # async def run_streaming_workflow(
    #     self,
    #     user_input: str,
    #     history: list | None,
    #     current_agent: str | None,
    # ) -> AsyncGenerator[Any, None]:
    #     """
    #     Main workflow (streaming) to run the agents with given user input, history, and current agent.

    #     TODO: we can allow a flexible hand-off architecture in future
    #     - can be achieved by saving the current agent
    #     - passing in entire context back to the current agent when the workflow resumes
    #     """

    #     logger.info(
    #         f"Running workflow with user_input: {user_input}, current_agent: {current_agent}"
    #     )

    #     try:
    #         wrapper = RunContextWrapper(
    #             context=StateContext(
    #                 current_agent=current_agent,
    #                 feature_id="test_test",
    #             )
    #         )

    #         # TODO: future when we have more agents
    #         # Init entry point agent
    #         if current_agent:
    #             agent = self.current_agent_mapping[current_agent]
    #         else:
    #             agent = self.jargon_agent

    #         # If have existing history, append new user message to it, else create new
    #         if history:
    #             logger.info(f"Received existing history with {len(history)} items.")
    #             history.append({"content": user_input, "role": "user"})

    #         else:
    #             logger.info("No existing history, starting new conversation.")
    #             history: list[TResponseInputItem] = [
    #                 {"content": user_input, "role": "user"}
    #             ]

    #         # Always init
    #         tool_output = None
    #         final_agents = {
    #             "report_generator_agent",
    #         }
    #         message = ""

    #         with trace("agent_service.run_streaming_workflow"):
    #             result = Runner.run_streamed(
    #                 agent, input=history, context=wrapper, max_turns=20
    #             )

    #             logger.info("Runner started, streaming events...")

    #             # Iterate through runner events
    #             async for event in result.stream_events():
    #                 if isinstance(event, RawResponsesStreamEvent):
    #                     """
    #                     Raw response event: raw events directly from the LLM, in OpenAI Response API format
    #                     For all the events, use `event.type` to retrieve the type of event
    #                     """
    #                     data = event.data
    #                     if isinstance(
    #                         data, ResponseTextDeltaEvent
    #                     ):  # streaming text of a single LLM output
    #                         message += data.delta  # collect the word by word output
    #                         response_dict = {
    #                             "event_type": EventType.DELTA_TEXT_EVENT,
    #                             "message": message,  # with latest delta message appended
    #                             "delta_message": data.delta,  # latest delta message
    #                             "data_type": None,
    #                             "data": None,
    #                             "history": None,
    #                             "agent_name": current_agent,
    #                         }

    #                         # yield "Raw event TextDelta"
    #                         yield AgentResponse(**response_dict)

    #                     elif isinstance(
    #                         data, ResponseContentPartDoneEvent
    #                     ):  # the end of a text output response
    #                         message += "\n"
    #                         response_dict = {
    #                             "event_type": EventType.COMPLETED_TEXT_EVENT,
    #                             "message": message,
    #                             "delta_message": None,
    #                             "data_type": None,
    #                             "data": None,
    #                             "history": None,
    #                             "agent_name": current_agent,
    #                         }

    #                         # yield "Raw event ContentPartDone"
    #                         yield AgentResponse(**response_dict)

    #                     else:  # other types of events
    #                         pass

    #                 elif isinstance(
    #                     event, AgentUpdatedStreamEvent
    #                 ):  # agent that is started / handed off to, e.g. triage_agent during init
    #                     wrapper.context.current_agent = (
    #                         event.new_agent.name
    #                     )  # set in context
    #                     current_agent = event.new_agent.name
    #                     response_dict = {
    #                         "event_type": EventType.NEW_AGENT_EVENT,
    #                         "message": message,
    #                         "data_type": None,
    #                         "data": None,
    #                         "history": None,
    #                         "agent_name": current_agent,  # name of the agent that is handed off to
    #                     }

    #                     yield AgentResponse(**response_dict)

    #                 elif isinstance(
    #                     event, RunItemStreamEvent
    #                 ):  # Higher level event, inform me when an item has been fully generated, tool call
    #                     """
    #                     e.g. handoff: after all raw events, handoff_requested -> handoff_occured (include 'source_agent', and target agent 'raw_item.output.assistant')
    #                     """
    #                     if isinstance(event.item, ToolCallItem):
    #                         response_dict = {
    #                             "event_type": EventType.TOOL_CALL_EVENT,
    #                             "message": event.item.raw_item.name,
    #                             "data_type": None,
    #                             "data": None,
    #                             "history": None,
    #                             "agent_name": event.item.agent.name,  # agent that called the tool
    #                         }

    #                         yield AgentResponse(**response_dict)

    #                     # other type for evemt.item: ToolCallItem, ToolCallOutputItem, MessageOutputItem, HandoffCallItem, HandoffOutputItem
    #                     elif isinstance(
    #                         event.item, ToolCallOutputItem
    #                     ):  # tool call output
    #                         # TODO: check for custom handling?
    #                         tool_output = event.item.output
    #                         tool_output_dict = json.loads(tool_output)
    #                         response_dict = {
    #                             "event_type": EventType.TOOL_CALL_OUTPUT_EVENT,
    #                             "message": None,
    #                             # TODO: shall we use data_type
    #                             # "data_type": wrapper.context.data_type,  # set by the individual agent during runtime
    #                             "data_type": None,
    #                             "data": tool_output_dict,
    #                             "history": None,
    #                             "agent_name": event.item.agent.name,  # agent that called the tool
    #                         }
    #                         wrapper.context.data_type = None

    #                         # yield "Tool call output"
    #                         yield AgentResponse(**response_dict)

    #                     # elif isinstance(event.item, MessageOutputItem):
    #                     if isinstance(event.item, MessageOutputItem):
    #                         print("message output item")
    #                         pass
    #                 else:
    #                     print("unknown event: ", event)
    #                     pass

    #         # TODO: more dynamic agent routing
    #         # current_agent = result.current_agent.name
    #         # # If current agent is one of the final_agents, or restart flag set to True, change current agent to triage_agent
    #         # if current_agent in final_agents or wrapper.context.restart:
    #         #     current_agent = "triage_agent"
    #         #     wrapper.context.restart = False

    #         # TODO: handle cases where handmade cache should be removed
    #         history = result.to_input_list()

    #         last_message = history[-1]["content"][0]["text"]

    #         response_dict = {
    #             "event_type": EventType.TERMINATING_EVENT,  # the end of the conversation
    #             "message": None,
    #             "data_type": None,
    #             "data": None,
    #             "history": history,  # the consolidated history of the whole call
    #             "agent_name": current_agent,
    #             # "memo": memo.model_dump(),
    #         }

    #         yield AgentResponse(**response_dict)

    #     except Exception as exc:
    #         logger.error(f"Error during run_workflow: {exc}", exc_info=True)
    #         response_dict = {
    #             "event_type": EventType.ERROR_EVENT,
    #             "message": None,
    #             "data_type": None,
    #             "data": {"type": exc.__class__.__name__, "message": str(exc)},
    #             "history": None,
    #             "agent_name": None,
    #         }
    #         yield AgentResponse(**response_dict)
