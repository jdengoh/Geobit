"""
Pydantic Schemas for Agent State and Context.
"""

from typing import List, Optional

from pydantic import BaseModel

from .evidence import Evidence
from .jargons import JargonQueryResult


class StateContext(BaseModel):
    """Context object for carrying state through the pipeline."""

    session_id: str
    current_agent: str
    retrieved_evidence: Optional[List[Evidence]] = None
    jargon_translation: Optional[JargonQueryResult] = None
