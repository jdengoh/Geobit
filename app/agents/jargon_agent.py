"""
Jargon Agent with Parallel Web Search - Optimized Context Saving
Using OpenAI Agents SDK - Agent as Tool Pattern
"""

import asyncio
import os
from typing import List, Optional

import aiohttp
from agents import Agent, RunContextWrapper, Runner, function_tool
from pydantic import BaseModel, Field


# Enhanced Pydantic Models
class JargonDetail(BaseModel):
    term: str = Field(description="The jargon term found")
    definition: Optional[str] = Field(
        default=None, description="Definition if found in database"
    )


class Source(BaseModel):
    title: Optional[str] = Field(description="The title of the source document.")
    link: Optional[str] = Field(description="The URL of the source.")


# Updated JargonSearchDetail
class JargonSearchDetail(BaseModel):
    term: str = Field(description="The jargon term found")
    definition: Optional[str] = Field(
        default=None, description="A summarized definition of the term."
    )
    sources: List[Source] = Field(
        default_factory=list, description="A list of source URLs and titles."
    )


# Now, update your main JargonQueryResult to use this new model for searched terms
class JargonQueryResult(BaseModel):
    detected_terms: List[JargonDetail] = Field(
        default=[], description="Terms found in database"
    )
    searched_terms: List[JargonSearchDetail] = Field(
        default=[], description="Terms searched on the web"
    )
    unknown_terms: List[JargonDetail] = Field(
        default=[], description="Terms not found or unclear"
    )


class WebSearchResult(BaseModel):
    """Result from web search agent"""

    query: str = Field(description="The search query used")
    success: bool = Field(description="Whether the search was successful")
    results: str = Field(description="Formatted search results or error message")
    sources_found: int = Field(default=0, description="Number of sources found")


class StateContext(BaseModel):
    """Context object for carrying state through the pipeline"""

    session_id: str
    current_agent: str
    jargon_translation: Optional[JargonQueryResult] = None


class FeatureArtifact(BaseModel):
    feature_name: str = Field(description="Original feature name with potential jargon")
    feature_description: str = Field(description="Detailed functionality description")


class StandardizedFeature(BaseModel):
    standardized_name: str = Field(description="Clear, jargon-free feature name")
    standardized_description: str = Field(description="Clean functionality description")


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


# ====================
# WEB SEARCH AGENT
# ====================


def _format_serper_results(response_data: dict, query: str) -> str:
    """Format Google Serper API response"""
    organic_results = response_data.get("organic", [])
    if not organic_results:
        return f"No results found for: {query}"

    results = []
    for i, result in enumerate(organic_results[:3], 1):
        title = result.get("title", "No title")
        snippet = result.get("snippet", "No description")
        link = result.get("link", "")
        formatted_result = (
            f"Result {i}:\nTitle: {title}\nSnippet: {snippet}\nLink: {link}"
        )
        results.append(formatted_result)

    return "\n\n".join(results)


async def _single_serper_search(
    query: str, max_retries: int = 3, retry_delay: int = 1
) -> str:
    """Performs a single Serper API search with retry logic."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "❌ SERPER_API_KEY not found in environment variables"

    payload = {"q": query, "num": 3}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://google.serper.dev/search", json=payload, headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return _format_serper_results(data, query)
                    elif response.status in [429, 500, 502, 503, 504]:
                        await asyncio.sleep(retry_delay)
        except Exception:
            await asyncio.sleep(retry_delay)

    return f"❌ Search failed after {max_retries} attempts."


@function_tool
async def parallel_web_search(
    ctx: RunContextWrapper[StateContext], terms: List[str]
) -> str:
    """
    Performs parallel web searches for a list of jargon terms.
    Updates the context with successful search results.
    """
    if not terms:
        return "No terms provided for web search."

    print(f"🌐 Starting parallel web searches for {len(terms)} terms...")

    # Create and run tasks for each term
    search_tasks = [
        _single_serper_search(f"{term} in software development") for term in terms
    ]

    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    successful_searches = []

    for term, result in zip(terms, results):
        if isinstance(result, str) and not result.startswith("❌"):
            successful_searches.append(JargonDetail(term=term, definition=result))
        else:
            print(f"❌ Web search failed for {term}.")

    if ctx.context and ctx.context.jargon_translation:
        # Add successful searches to the searched_terms list
        ctx.context.jargon_translation.searched_terms.extend(successful_searches)

        # Remove terms from unknown_terms if they were successfully searched
        searched_terms_set = {detail.term for detail in successful_searches}
        ctx.context.jargon_translation.unknown_terms = [
            term
            for term in ctx.context.jargon_translation.unknown_terms
            if term.term not in searched_terms_set
        ]

    return f"✅ Successfully processed {len(successful_searches)} terms. {len(ctx.context.jargon_translation.unknown_terms)} terms remain unknown."


# ====================
# JARGON AGENT
# ====================
@function_tool
async def query_jargon_database(
    ctx: RunContextWrapper[StateContext], terms: List[str]
) -> JargonQueryResult:
    """Query the internal jargon database for term definitions."""
    print(f"🔍 Querying jargon database for terms: {terms}")

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

    # Initialize or update state context
    if ctx.context:
        ctx.context.jargon_translation = JargonQueryResult(
            detected_terms=detected_terms, unknown_terms=unknown_terms
        )

    print(
        f"✅ Found {len(detected_terms)} known terms, {len(unknown_terms)} unknown terms"
    )
    return ctx.context.jargon_translation


def jargon_agent_prompt(
    context_wrapper: RunContextWrapper[StateContext], agent: Agent[StateContext]
) -> str:
    """Instructions for the jargon translation agent"""
    return """
You are a Jargon Translation Agent for TikTok's geo-regulation compliance system.

STEP-BY-STEP PROCESS:
1. IDENTIFY: Extract ALL acronyms and jargon terms from the feature name and description.
2. DATABASE QUERY: Use the query_jargon_database tool ONCE with all identified terms.
3. WEB SEARCH: If the query_jargon_database tool's result has unknown terms, use the parallel_web_search tool ONCE with the list of unknown terms to get definitions.
4. CREATE OUTPUT: Combine all definitions (from the database and web searches) to generate standardized, jargon-free versions of the feature name and description.
5. FINAL RESPONSE: The final response must be an object of type StandardizedFeature.
"""


def create_jargon_agent() -> Agent[StateContext]:
    """Create the Jargon Agent with the new parallel search tool."""
    return Agent[StateContext](
        name="Jargon Translation Agent",
        instructions=jargon_agent_prompt,
        tools=[query_jargon_database, parallel_web_search],
        output_type=StandardizedFeature,
        model="gpt-5-nano",
    )


# Test with the new approach
async def test_new_jargon_agent():
    """Test the Jargon Agent with optimized parallel search."""
    sample_input = FeatureArtifact(
        feature_name="ASL-Enhanced PF with CustomAPI and XRAY System",
        feature_description="This feature implements ASL logic with Snowcap integration and XRAY module for testing.",
    )

    # We will use the same context and initial input
    context = StateContext(session_id="new_context_001", current_agent="jargon_agent")

    jargon_agent = create_jargon_agent()

    print("🚀 Starting Jargon Agent with Parallel Web Searches...")
    print(f"📥 Input: {sample_input.feature_name}")
    print()

    try:
        result = await Runner.run(
            jargon_agent,
            f"Translate all jargon in this feature: {sample_input.model_dump_json()}",
            context=context,
            max_turns=5,  # Fewer turns needed with the optimized workflow
        )

        print("\n✅ Final Results:")
        print(f"📝 Standardized Name: {result.final_output.standardized_name}")
        print(
            f"📄 Standardized Description: {result.final_output.standardized_description}"
        )

        if context.jargon_translation:
            jt = context.jargon_translation
            print("\n🔍 Detailed Jargon Analysis:")
            if jt.detected_terms:
                print(f"   ✅ Database Terms ({len(jt.detected_terms)}):")
                for term in jt.detected_terms:
                    print(f"      • {term.term} → {term.definition}")
            if jt.searched_terms:
                print(f"   🌐 Web Search Results ({len(jt.searched_terms)}):")
                for term in jt.searched_terms:
                    print(f"      • {term.term} → Found via web search")
                    print(f"        Definition: {term.definition[:100]}...")
            if jt.unknown_terms:
                print(f"   ❓ Still Unknown ({len(jt.unknown_terms)}):")
                for term in jt.unknown_terms:
                    print(f"      • {term.term} → Could not define")

        print(context.model_dump_json())
        return result.final_output, context

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    print("💡 This version uses a single, optimized tool for all web searches.")
    asyncio.run(test_new_jargon_agent())
