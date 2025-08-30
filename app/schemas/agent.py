from typing import Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    feature_name: str = Field(..., description="Feature title or name")
    feature_description: str = Field(..., description="Detailed feature description")

    # Optional for conversation continuity
    # history: Optional[list] = Field(
    #     default=None, description="Previous analysis history"
    # )
    feature_id: Optional[str] = Field(
        default=None, description="Optional session identifier"
    )
class AgentStreamResponse(BaseModel):
    agent_name: str
    event: str  # ← Change from event_type to event
    payload: Optional[dict] = None  # ← Top-level payload
    stage: Optional[str] = None
    message: Optional[str] = None
    terminating: bool = False