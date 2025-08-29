"""
Jargon Agent with Web Search Agent as a Tool.
"""

import os
import sys
from pathlib import Path
import logging
from typing import List

from agents import Agent, RunContextWrapper, function_tool

# Load environment variables from .env file in the root directory
try:
    from dotenv import load_dotenv
    # Get the path to the root directory (2 levels up from this file)
    root_dir = Path(__file__).parent.parent.parent
    env_file = root_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded .env from: {env_file}")
    else:
        print(f"❌ .env file not found at: {env_file}")
except ImportError:
    print("❌ python-dotenv not installed")
except Exception as e:
    print(f"❌ Error loading .env: {e}")

# Verify that the API key is loaded
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print(f"✅ OPENAI_API_KEY loaded (length: {len(api_key)})")
else:
    print("❌ OPENAI_API_KEY not found in environment variables")

from app.agent.schemas.agents import StateContext
from app.agent.schemas.jargons import (
    JargonDetail,
    JargonQueryResult,
    StandardizedFeature,
)
from app.agent.web_search_agent import create_web_search_agent

logger = logging.getLogger(__name__)


# TikTok Jargon Database (remains the same)
JARGON_DATABASE = {
    "NR": "Not recommended",
    "PF": "Personalized feed",
    "GH": "Geo-handler; a module responsible for routing features based on user region",
    "CDS": "Compliance Detection System",
    "DRT": "Data retention threshold; duration for which logs can be stored",
    "LCP": "Local compliance policy",
    "REDLINE": "Flag for legal review",
    "SOFTBLOCK": "A user-level limitation applied silently without notifications",
    "SPANNER": "A synthetic name for a rule engine",
    "SHADOWMODE": "Deploy feature in non-user-impact way to collect analytics only",
    "T5": "Tier 5 sensitivity data; more critical than T1-T4 in this internal taxonomy",
    "ASL": "Age-sensitive logic",
    "GLOW": "A compliance-flagging status, internally used to indicate geo-based alerts",
    "NSP": "Non-shareable policy (content should not be shared externally)",
    "JELLYBEAN": "Feature name for internal parental control system",
    "ECHOTRACE": "Log tracing mode to verify compliance routing",
    "BB": "Baseline Behavior; standard user behavior used for anomaly detection",
    "SNOWCAP": "A synthetic codename for the child safety policy framework",
    "FR": "Feature rollout status",
    "IMT": "Internal monitoring trigger",
    "COPPA": "Children's Online Privacy Protection Act",
    "GDPR": "General Data Protection Regulation",
}


@function_tool
async def query_jargon_database(
    ctx: RunContextWrapper[StateContext], terms: List[str]
) -> JargonQueryResult:
    """Query the internal jargon database for term definitions."""
    logger.info(f"🔍 Querying jargon database for terms: {terms}")

    detected_terms = []
    unknown_terms = []

    for term in terms:
        term_key = term.upper()
        if term_key in JARGON_DATABASE:
            detected_terms.append(
                JargonDetail(term=term, definition=JARGON_DATABASE[term_key])
            )
        else:
            unknown_terms.append(JargonDetail(term=term, definition=None))

    if ctx.context:
        ctx.context.jargon_translation = JargonQueryResult(
            detected_terms=detected_terms, unknown_terms=unknown_terms
        )

    logger.info(
        f"✅ Found {len(detected_terms)} known terms, {len(unknown_terms)} unknown terms"
    )
    return ctx.context.jargon_translation.model_dump_json()


def jargon_agent_prompt(
    context_wrapper: RunContextWrapper[StateContext], agent: Agent[StateContext]
) -> str:
    """Instructions for the jargon translation agent."""
    return """
    You are a Jargon Compliance & Translation Specialist. Your primary mission is to ensure that all internal technical documentation is clear, accurate, and ready for legal and compliance review. Your translations must be precise, jargon-free, and grounded in definitive knowledge.

    Follow this strict, non-negotiable workflow for every feature artifact:

    1.  **Identify**: Systematically extract all acronyms and jargon terms from the provided feature name and description. This list must be comprehensive.

    2.  **Database Query**: Invoke the `query_jargon_database` tool **exactly once** with the complete list of terms identified in the previous step. This is your first and most critical action. The tool will provide official definitions for known terms and identify any that are unknown.

    3.  **Conditional External Search**:
        * You **must** inspect the output of the `query_jargon_database` tool.
        * **ONLY IF** the `unknown_terms` list is non-empty, you will use the `web_search_agent` tool.
        * You **must strictly pass only** the terms from the `unknown_terms` list to the `web_search_agent`. Do not search for terms that were already successfully defined by the database.

    4.  **Finalize**: Your final output **must be a single, well-structured `StandardizedFeature` JSON object**. Do not include any other text, commentary, or conversational remarks. Your only output is the JSON itself.
    """


def create_jargon_agent():
    """Create the Jargon Agent with Web Search Agent as a tool."""
    web_search_agent = create_web_search_agent()
    web_search_tool = web_search_agent.as_tool(
        tool_name="web_search_agent",
        tool_description="Searches for and summarizes a list of jargon terms. Input a list of strings.",
    )
    return Agent(
        name="Jargon Translation Agent",
        instructions=jargon_agent_prompt,
        tools=[query_jargon_database, web_search_tool],
        output_type=StandardizedFeature,
        model="gpt-5-nano",
    )
