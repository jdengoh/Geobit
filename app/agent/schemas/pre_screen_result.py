from typing import List, Literal
from pydantic import BaseModel, Field

PreScreenResultType = Literal["acceptable","problematic","needs_human_review"]

class PreScreenResult(BaseModel):
    decision: PreScreenResultType
    reasoning: str
    
