"""
Jargon Agent with Separate Web Search Agent - Fixed Context Saving
Using OpenAI Agents SDK - Agent as Tool Pattern
"""

from pprint import pprint
from agents import Agent, function_tool, Runner, RunContextWrapper, ModelSettings
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Set
import asyncio
import json
import os
import aiohttp
import re


# Enhanced Pydantic Models
class JargonDetail(BaseModel):
    term: str = Field(description="The jargon term found")
    definition: Optional[str] = Field(default=None, description="Definition if found in database")


class JargonQueryResult(BaseModel):
    """Structured result from jargon database query"""
    detected_terms: List[JargonDetail] = Field(default=[], description="Terms found in database")
    searched_terms: List[JargonDetail] = Field(default=[], description="Terms searched on the web")
    unknown_terms: List[JargonDetail] = Field(default=[], description="Terms not found or unclear")


class WebSearchResult(BaseModel):
    """Result from web search agent"""
    query: str = Field(description="The search query used")
    success: bool = Field(description="Whether the search was successful")
    results: str = Field(description="Formatted search results or error message")
    sources_found: int = Field(default=0, description="Number of sources found")

# TODO: move StateContext out and add in sources possibly
class StateContext(BaseModel):
    """Context object for carrying state through the pipeline"""
    session_id: str
    current_agent: str
    jargon_translation: Optional[JargonQueryResult] = None
    # sources: Optional[List[str]] = None
    # queried_terms: Set[str] = Field(default_factory=set)

# TODO: add in artifact after processing
# Data Models 
class FeatureArtifact(BaseModel):
    feature_name: str = Field(description="Original feature name with potential jargon")
    feature_description: str = Field(description="Detailed functionality description")


class StandardizedFeature(BaseModel):
    standardized_name: str = Field(description="Clear, jargon-free feature name")
    standardized_description: str = Field(description="Clean functionality description")


# TikTok Jargon Database
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
    "GDPR": "General Data Protection Regulation"
}


# ====================
# WEB SEARCH AGENT
# ====================

@function_tool
async def google_serper_search(
    ctx: RunContextWrapper[StateContext],
    query: str
) -> str:
    """Search using Google Serper API."""
    print(f"🔍 Serper API search: {query}")
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return f"❌ SERPER_API_KEY not found in environment variables"
    
    payload = {"q": query, "num": 3}
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://google.serper.dev/search", 
                json=payload,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return _format_serper_results(data, query)
                else:
                    return f"❌ Serper API error: {response.status}"
    
    except Exception as e:
        return f"❌ Search failed: {str(e)}"


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
        
        formatted_result = f"Result {i}:\nTitle: {title}\nSnippet: {snippet}\nLink: {link}"
        results.append(formatted_result)
    
    formatted_results = "\n\n".join(results)
    return f"Search results for '{query}':\n\n{formatted_results}"


def web_search_agent_prompt(
    context_wrapper: RunContextWrapper[StateContext], 
    agent: Agent[StateContext]
) -> str:
    """Instructions for the web search agent"""
    return """
You are a Web Search Agent specialized in finding definitions for technical terms and jargon.

Your task:
1. Use google_serper_search tool to search for the given query
2. Analyze the search results to extract a clear, concise definition
3. Focus on technical definitions suitable for business/compliance use
4. If search fails or no good results, clearly indicate failure

Provide a structured response with:
- The search query used
- Whether the search was successful
- A clear definition based on the results (or error message)
- Number of sources found

Keep definitions business-friendly and technically accurate.
"""


def create_web_search_agent() -> Agent[StateContext]:
    """Create the Web Search Agent"""
    return Agent[StateContext](
        name="Web Search Agent",
        instructions=web_search_agent_prompt,
        tools=[google_serper_search],
        output_type=WebSearchResult,
        model="gpt-5-nano"
    )


# ====================
# JARGON AGENT
# ====================

@function_tool
async def query_jargon_database(
    ctx: RunContextWrapper[StateContext], 
    terms: List[str]
) -> JargonQueryResult:
    """Query the internal jargon database for term definitions."""
    print(f"🔍 Querying jargon database for terms: {terms}")
    
    detected_terms = []
    unknown_terms = []
    
    for term in terms:
        term_key = term.upper()
        
        if term_key in JARGON_DATABASE:
            detected_terms.append(JargonDetail(
                term=term,
                definition=JARGON_DATABASE[term_key]
            ))
        else:
            unknown_terms.append(JargonDetail(
                term=term,
                definition=None
            ))
    
    result = JargonQueryResult(
        detected_terms=detected_terms,
        searched_terms=[],
        unknown_terms=unknown_terms
    )
    
    print(f"✅ Found {len(detected_terms)} known terms, {len(unknown_terms)} unknown terms")
    
    # Update state context
    if ctx.context:
        ctx.context.jargon_translation = result
        # for term in terms:
        #     ctx.context.queried_terms.add(term.upper())
    
    return result


@function_tool
async def save_web_search_result(
    ctx: RunContextWrapper[StateContext],
    jargon_term: str,
    search_result: WebSearchResult
) -> str:
    """
    Save web search results to context for proper tracking.
    
    Args:
        jargon_term: The actual jargon term that was searched
        search_result: The WebSearchResult from the web search agent
        
    Returns:
        Status message
    """
    print(f"💾 Saving web search result for term: {jargon_term}")
    
    if not ctx.context or not ctx.context.jargon_translation:
        return "❌ No jargon translation context available to save results"
    
    if search_result.success:
        # Create a JargonDetail with the search results
        searched_detail = JargonDetail(
            term=jargon_term,
            definition=search_result.results
        )
        
        # Add to searched_terms
        ctx.context.jargon_translation.searched_terms.append(searched_detail)
        
        # Remove from unknown_terms if it was there
        ctx.context.jargon_translation.unknown_terms = [
            term for term in ctx.context.jargon_translation.unknown_terms 
            if term.term != jargon_term
        ]
        
        # TODO: removed sources
        # Update sources
        # sources = ctx.context.sources or []
        # if "Google Serper API" not in sources:
        #     sources.append("Google Serper API")
        # ctx.context.sources = sources
        
        print(f"✅ Saved web search result for {jargon_term}")
        return f"✅ Successfully saved web search definition for {jargon_term}"
    
    else:
        # Search failed - ensure term stays in unknown_terms
        unknown_terms = [term.term for term in ctx.context.jargon_translation.unknown_terms]
        if jargon_term not in unknown_terms:
            ctx.context.jargon_translation.unknown_terms.append(
                JargonDetail(term=jargon_term, definition=None)
            )
        
        print(f"❌ Web search failed for {jargon_term}, marked as unknown")
        return f"❌ Web search failed for {jargon_term}, marked as unknown"


def jargon_agent_prompt(
    context_wrapper: RunContextWrapper[StateContext], 
    agent: Agent[StateContext]
) -> str:
    """Instructions for the jargon translation agent"""
    return """
You are a Jargon Translation Agent for TikTok's geo-regulation compliance system.

STEP-BY-STEP PROCESS:

1. IDENTIFY: Extract ALL jargon terms from the feature name and description

2. DATABASE QUERY: Use query_jargon_database tool ONCE with ALL identified terms

3. WEB SEARCH: For each unknown term:
   a) Use web_search_agent tool with query like "TERMNAME in software development"
   b) Use save_web_search_result tool to save the results to context
   c) Extract the jargon term name from your search query when saving

4. CREATE OUTPUT: Generate standardized versions using all available definitions

IMPORTANT WORKFLOW:
- For each unknown term: web_search_agent → save_web_search_result → move to next term
- Always save web search results immediately after getting them
- Extract the actual term name (e.g., "XRAY" from "XRAY in software development")

Example for unknown term "XRAY":
1. Call web_search_agent with "XRAY in software development" 
2. Call save_web_search_result with jargon_term="XRAY" and the search result
3. Continue to next unknown term

Your goal: Transform technical jargon into clear, compliance-ready language with proper result tracking.
"""


def create_jargon_agent() -> Agent[StateContext]:
    """Create the Jargon Agent with Web Search Agent and result saving"""
    
    # Create the web search agent
    web_search_agent = create_web_search_agent()
    
    # Convert web search agent to a tool
    web_search_tool = web_search_agent.as_tool(
        tool_name="web_search_agent",
        tool_description="Search the web for jargon term definitions. Provide the search query and get structured results."
    )
    
    return Agent[StateContext](
        name="Jargon Translation Agent",
        instructions=jargon_agent_prompt,
        tools=[
            query_jargon_database, 
            web_search_tool,
            save_web_search_result  # New tool to save results!
        ],
        output_type=StandardizedFeature,
        model="gpt-5-nano"
    )


# Test with proper result saving
async def test_fixed_context_saving():
    """Test the Jargon Agent with proper context saving"""
    
    sample_input = FeatureArtifact(
        feature_name="ASL-Enhanced PF with CustomAPI and XRAY System",
        feature_description="This feature implements ASL logic with Snowcap integration and XRAY module for testing."
    )
    
    context = StateContext(
        session_id="fixed_context_001",
        current_agent="jargon_agent"
    )
    
    jargon_agent = create_jargon_agent()
    
    print("🚀 Starting Jargon Agent with Fixed Context Saving...")
    print(f"📥 Input: {sample_input.feature_name}")
    print()
    
    try:
        result = await Runner.run(
            jargon_agent,
            f"Translate jargon and save web search results properly: {sample_input.model_dump_json()}",
            context=context,
            max_turns=8  # More turns for web search + saving
        )
        
        print("\n✅ Final Results:")
        print(f"📝 Standardized Name: {result.final_output.standardized_name}")
        print(f"📄 Standardized Description: {result.final_output.standardized_description}")
        
        # Show detailed breakdown
        if context.jargon_translation:
            jt = context.jargon_translation
            print(f"\n🔍 Detailed Jargon Analysis:")
            
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
        
        # if context.sources:
        #     print(f"\n📚 Sources Used: {', '.join(context.sources)}")
        
        pprint(context.model_dump())
        return result.final_output, context
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    print("💡 This version properly saves web search results to context")
    print("💡 Uses save_web_search_result tool to track definitions")
    asyncio.run(test_fixed_context_saving())