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
from app.agent.retrieval_agent import create_retrieval_agent, retrieve_evidence
from app.agent.review_agent import create_llm_reviewer
from app.agent.schemas.agents import StateContext


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
        # self.triage = create_triage_agent()
        # self.triage_agent = create_triage_agent()
        self.jargon_agent = create_jargon_agent()
        # analysis stack
        self.analysis_planner = create_analysis_planner()
        self.analysis_synth = create_analysis_synthesizer()
        self.retrieval_agent = create_retrieval_agent()
        self.review_agent = create_llm_reviewer()


        self.current_agent_mapping = {
            # "triage_agent": self.triage_agent,
            "jargon_agent": self.jargon_agent,
            # "analysis_planner_agent": self.analysis_planner_agent,
            # "analysis_synthesizer_agent": self.analysis_synthesizer_agent,
        }

        # self.jargon_agent.handoffs = [self.analysis_planner_agent]

        # TODO: for a proper hand-off architecture
        # self.triage.handoffs = [self.compliance_classifier]
        # self.compliance_classifier.handoffs = [self.context_enricher, self.regulation_identifier]
        # self.context_enricher.handoffs = [self.regulation_identifier]

    def get_agent(self):
        """
        Return all available agents in the system.
        """
        agents = {
            # TODO: no triage for now
            "Jargon Agent": self.jargon_agent,
            "Analysis Planner": self.analysis_planner,
            "Analysis Synthesizer": self.analysis_synth,
            "Retrieval Agent": self.retrieval_agent,
            "Reviewer Agent": self.review_agent
        }
        return agents

    async def run_streaming_workflow(
        self,
        user_input: str,
        history: list | None,
        current_agent: str | None,
    ) -> AsyncGenerator[Any, None]:
        """
        Main workflow (streaming) to run the agents with given user input, history, and current agent.

        TODO: we can allow a flexible hand-off architecture in future
        - can be achieved by saving the current agent
        - passing in entire context back to the current agent when the workflow resumes
        """

        logger.info(
            f"Running workflow with user_input: {user_input}, current_agent: {current_agent}"
        )

        try:
            wrapper = RunContextWrapper(
                context=StateContext(
                    current_agent=current_agent,
                    restart=False,
                    session_id="test_test"
                )
            )

            # TODO: future when we have more agents
            # Init entry point agent
            if current_agent:
                agent = self.current_agent_mapping[current_agent]
            else:
                agent = self.jargon_agent

            # If have existing history, append new user message to it, else create new
            if history:
                logger.info(f"Received existing history with {len(history)} items.")
                history.append({"content": user_input, "role": "user"})

            else:
                logger.info("No existing history, starting new conversation.")
                history: list[TResponseInputItem] = [
                    {"content": user_input, "role": "user"}
                ]

            # Always init
            tool_output = None
            final_agents = {
                "report_generator_agent",
            }
            message = ""

            with trace("agent_service.run_streaming_workflow"):
                result = Runner.run_streamed(
                    agent, input=history, context=wrapper, max_turns=20
                )

                logger.info("Runner started, streaming events...")

                # Iterate through runner events
                async for event in result.stream_events():
                    if isinstance(event, RawResponsesStreamEvent):
                        """
                        Raw response event: raw events directly from the LLM, in OpenAI Response API format
                        For all the events, use `event.type` to retrieve the type of event
                        """
                        data = event.data
                        if isinstance(
                            data, ResponseTextDeltaEvent
                        ):  # streaming text of a single LLM output
                            message += data.delta  # collect the word by word output
                            response_dict = {
                                "event_type": EventType.DELTA_TEXT_EVENT,
                                "message": message,  # with latest delta message appended
                                "delta_message": data.delta,  # latest delta message
                                "data_type": None,
                                "data": None,
                                "history": None,
                                "agent_name": current_agent,
                            }

                            # yield "Raw event TextDelta"
                            yield AgentResponse(**response_dict)

                        elif isinstance(
                            data, ResponseContentPartDoneEvent
                        ):  # the end of a text output response
                            message += "\n"
                            response_dict = {
                                "event_type": EventType.COMPLETED_TEXT_EVENT,
                                "message": message,
                                "delta_message": None,
                                "data_type": None,
                                "data": None,
                                "history": None,
                                "agent_name": current_agent,
                            }

                            # yield "Raw event ContentPartDone"
                            yield AgentResponse(**response_dict)

                        else:  # other types of events
                            pass

                    elif isinstance(
                        event, AgentUpdatedStreamEvent
                    ):  # agent that is started / handed off to, e.g. triage_agent during init
                        wrapper.context.current_agent = (
                            event.new_agent.name
                        )  # set in context
                        current_agent = event.new_agent.name
                        response_dict = {
                            "event_type": EventType.NEW_AGENT_EVENT,
                            "message": message,
                            "data_type": None,
                            "data": None,
                            "history": None,
                            "agent_name": current_agent,  # name of the agent that is handed off to
                        }

                        yield AgentResponse(**response_dict)

                    elif isinstance(
                        event, RunItemStreamEvent
                    ):  # Higher level event, inform me when an item has been fully generated, tool call
                        """
                        e.g. handoff: after all raw events, handoff_requested -> handoff_occured (include 'source_agent', and target agent 'raw_item.output.assistant')
                        """
                        if isinstance(event.item, ToolCallItem):
                            response_dict = {
                                "event_type": EventType.TOOL_CALL_EVENT,
                                "message": event.item.raw_item.name,
                                "data_type": None,
                                "data": None,
                                "history": None,
                                "agent_name": event.item.agent.name,  # agent that called the tool
                            }

                            yield AgentResponse(**response_dict)

                        # other type for evemt.item: ToolCallItem, ToolCallOutputItem, MessageOutputItem, HandoffCallItem, HandoffOutputItem
                        elif isinstance(
                            event.item, ToolCallOutputItem
                        ):  # tool call output
                            # TODO: check for custom handling?
                            tool_output = event.item.output
                            tool_output_dict = json.loads(tool_output)
                            response_dict = {
                                "event_type": EventType.TOOL_CALL_OUTPUT_EVENT,
                                "message": None,
                                # TODO: shall we use data_type
                                # "data_type": wrapper.context.data_type,  # set by the individual agent during runtime
                                "data_type": None,
                                "data": tool_output_dict,
                                "history": None,
                                "agent_name": event.item.agent.name,  # agent that called the tool
                            }
                            wrapper.context.data_type = None

                            # yield "Tool call output"
                            yield AgentResponse(**response_dict)

                        # elif isinstance(event.item, MessageOutputItem):
                        if isinstance(event.item, MessageOutputItem):
                            print("message output item")
                            pass
                    else:
                        print("unknown event: ", event)
                        pass

            # TODO: more dynamic agent routing
            # current_agent = result.current_agent.name
            # # If current agent is one of the final_agents, or restart flag set to True, change current agent to triage_agent
            # if current_agent in final_agents or wrapper.context.restart:
            #     current_agent = "triage_agent"
            #     wrapper.context.restart = False

            # TODO: handle cases where handmade cache should be removed
            history = result.to_input_list()

            last_message = history[-1]["content"][0]["text"]

            response_dict = {
                "event_type": EventType.TERMINATING_EVENT,  # the end of the conversation
                "message": None,
                "data_type": None,
                "data": None,
                "history": history,  # the consolidated history of the whole call
                "agent_name": current_agent,
                # "memo": memo.model_dump(),
            }

            yield AgentResponse(**response_dict)

        except Exception as exc:
            logger.error(f"Error during run_workflow: {exc}", exc_info=True)
            response_dict = {
                "event_type": EventType.ERROR_EVENT,
                "message": None,
                "data_type": None,
                "data": {"type": exc.__class__.__name__, "message": str(exc)},
                "history": None,
                "agent_name": None,
            }
            yield AgentResponse(**response_dict)
