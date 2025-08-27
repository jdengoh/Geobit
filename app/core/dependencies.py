from fastapi import Request

from app.config import CONFIG_AGENT_SERVICE
from app.services.agent_service import AgentService

# from app.database.db import get_db

# Define dependencies here



def get_agent_service(request: Request) -> AgentService:

    agent_service: AgentService = getattr(request.app.state, CONFIG_AGENT_SERVICE, None)
    if agent_service is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent service not initialized",
        )
    return agent_service
