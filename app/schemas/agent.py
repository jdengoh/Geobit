from typing import Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    title: str = Field(..., description="Feature title or name")
    description: str = Field(..., description="Detailed feature description")

    # Optional for conversation continuity
    history: Optional[list] = Field(
        default=None, description="Previous analysis history"
    )
    session_id: Optional[str] = Field(
        default=None, description="Optional session identifier"
    )
