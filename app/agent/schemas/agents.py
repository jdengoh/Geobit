"""
Pydantic Schemas for Agent State and Context.
"""

from typing import Optional

from pydantic import BaseModel

from .jargons import JargonQueryResult


class StateContext(BaseModel):
    """Context object for carrying state through the pipeline."""

    session_id: str
    current_agent: str
    jargon_translation: Optional[JargonQueryResult] = None
