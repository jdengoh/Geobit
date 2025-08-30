"""
Web Search Agent with Parallel Web Search Tool for Legal Evidence Retrieval.
"""

import asyncio
import logging
import os
import re
from typing import List

import aiohttp
from agents import Agent, RunContextWrapper, function_tool
from openai import AsyncOpenAI
from schemas.evidence import Evidence, Finding, RetrievalNeed

logger = logging.getLogger(__name__)


# Helper functions for data processing
def _format_serper_results(response_data: dict, query: str) -> str:
    """Formats Google Serper API response into a readable string."""
    organic_results = response_data.get("organic", [])
    if not organic_results:
        return f"No results found for: {query}"
    
    results = []
    for i, result in enumerate(organic_results[:5], 1):  # Get top 5 results for legal research
        title = result.get("title", "No title")
        snippet = result.get("snippet", "No description")
        link = result.get("link", "")
        formatted_result = (
            f"Result {i}:\nTitle: {title}\nSnippet: {snippet}\nLink: {link}"
        )
        results.append(formatted_result)
    return "\n\n".join(results)


def _extract_evidence_from_results(raw_results: str, retrieval_need: RetrievalNeed) -> List[Evidence]:
    """Parses search results to extract relevant legal evidence snippets."""
    evidence_list = []
    
    # Pattern to extract individual results
    result_pattern = re.compile(r"Result \d+:\nTitle: (.+?)\nSnippet: (.+?)\nLink: (.+?)(?=\n\nResult|\Z)", re.DOTALL)
    
    for match in result_pattern.finditer(raw_results):
        title, snippet, link = match.groups()
        
        # Clean up the extracted text
        title = title.strip()
        snippet = snippet.strip()
        link = link.strip()
        
        # Create evidence if snippet contains relevant legal information
        if _is_relevant_legal_content(snippet, retrieval_need):
            evidence = Evidence(
                kind="web",
                ref=link,
                snippet=f"{title}: {snippet}"
            )
            evidence_list.append(evidence)
    
    return evidence_list


def _is_relevant_legal_content(snippet: str, retrieval_need: RetrievalNeed) -> bool:
    """Determines if a snippet contains relevant legal content based on the retrieval need."""
    snippet_lower = snippet.lower()
    
    # Check for legal-related keywords
    legal_keywords = [
        "law", "legal", "regulation", "statute", "compliance", "requirement",
        "code", "act", "amendment", "policy", "rule", "mandate", "jurisdiction",
        "federal", "state", "local", "court", "enforce", "violation", "penalty"
    ]
    
    has_legal_content = any(keyword in snippet_lower for keyword in legal_keywords)
    
    # Check for must-have tags in the content
    must_tags_present = True
    for tag in retrieval_need.must_tags:
        tag_keywords = _extract_keywords_from_tag(tag)
        if not any(keyword in snippet_lower for keyword in tag_keywords):
            must_tags_present = False
            break
    
    return has_legal_content and must_tags_present


def _extract_keywords_from_tag(tag: str) -> List[str]:
    """Converts tags into searchable keywords."""
    tag_mappings = {
        "jurisdiction_ut": ["utah", "ut", "state of utah"],
        "minor_protection": ["minor", "child", "children", "underage", "youth"],
        "curfew": ["curfew", "time restriction", "hours"],
        "child_safety": ["child safety", "minor safety", "youth protection", "child protection"],
        "age_gating": ["age verification", "age gate", "age restriction"],
        "federal_law": ["federal", "nationwide", "congress", "fcc", "ftc"],
        "geo_enforcement": ["geographic", "location", "territorial", "boundary"],
        "jurisdiction": ["jurisdiction", "authority", "legal authority", "court"]
    }
    
    return tag_mappings.get(tag, [tag.replace("_", " ")])


async def _get_llm_evidence_extraction(
    client: AsyncOpenAI, 
    retrieval_need: RetrievalNeed, 
    raw_results: str
) -> List[Evidence]:
    """Uses LLM to extract and format relevant legal evidence from search results."""
    prompt = f"""
    You are a legal research assistant. Extract relevant legal evidence from the following search results.
    
    Query: {retrieval_need.query}
    Required tags: {retrieval_need.must_tags}
    Preferred tags: {retrieval_need.nice_to_have_tags}
    
    Search Results:
    {raw_results}
    
    Instructions:
    1. Identify snippets that contain legal requirements, regulations, or compliance information
    2. Focus on content that matches the required tags: {retrieval_need.must_tags}
    3. Extract concise, relevant quotes (2-3 sentences max per evidence)
    4. Include the source URL for each piece of evidence
    
    Format your response as a JSON list of evidence objects, each with:
    - "kind": "web"
    - "ref": "URL"
    - "snippet": "relevant legal text excerpt"
    
    Only include evidence that directly relates to the legal requirements being searched.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        import json
        response_data = json.loads(response.choices[0].message.content)
        
        evidence_list = []
        if "evidence" in response_data and isinstance(response_data["evidence"], list):
            for item in response_data["evidence"]:
                if all(key in item for key in ["kind", "ref", "snippet"]):
                    evidence_list.append(Evidence(
                        kind=item["kind"],
                        ref=item["ref"],
                        snippet=item["snippet"]
                    ))
        
        return evidence_list
        
    except Exception as e:
        logger.info(f"❌ LLM evidence extraction failed: {e}")
        # Fallback to manual extraction
        return _extract_evidence_from_results(raw_results, retrieval_need)


async def _single_legal_search(
    client: AsyncOpenAI, 
    retrieval_need: RetrievalNeed, 
    max_retries: int, 
    retry_delay: int
) -> List[Evidence]:
    """Handles a single legal search request and evidence extraction."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.warning("❌ SERPER_API_KEY not found")
        return []

    # Enhance query for legal content
    enhanced_query = f"{retrieval_need.query} legal requirements regulations compliance law"
    
    payload = {"q": enhanced_query, "num": 3}
    print(payload)
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    raw_results = ""

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://google.serper.dev/search", 
                    json=payload, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_results = _format_serper_results(data, retrieval_need.query)
                        break
                    elif response.status in [429, 500, 502, 503, 504]:
                        logger.info(f"⏳ Rate limited/server error, retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.warning(f"❌ Search failed with status {response.status}")
                        break
        except Exception as e:
            logger.info(f"⚠️ Search attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

    if not raw_results or raw_results.startswith("No results found"):
        logger.info(f"❌ No results found for query: {retrieval_need.query}")
        return []

    logger.info(f"🔍 Search results obtained for: {retrieval_need.query}")
    
    # Extract evidence using LLM
    evidence_list = await _get_llm_evidence_extraction(client, retrieval_need, raw_results)
    
    logger.info(f"✅ Extracted {len(evidence_list)} pieces of evidence for: {retrieval_need.query}")
    return evidence_list


@function_tool
async def multi_legal_evidence_search(
    ctx: RunContextWrapper,
    retrieval_needs: List[RetrievalNeed],
    max_retries: int = 3,
    retry_delay: int = 65,
) -> List[Evidence]:
    """
    Performs parallel legal evidence searches based on retrieval needs.
    Returns a consolidated list of Evidence objects.
    """
    logger.info(f"🌐 Starting parallel legal evidence searches for {len(retrieval_needs)} queries.")

    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Create search tasks
    tasks = [
        _single_legal_search(openai_client, need, max_retries, retry_delay) 
        for need in retrieval_needs
    ]
    
    # Execute searches in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Consolidate all evidence
    all_evidence = []
    for i, result in enumerate(results):
        if isinstance(result, list):
            all_evidence.extend(result)
            logger.info(f"✅ Query {i+1} returned {len(result)} evidence pieces")
        else:
            logger.error(f"❌ Query {i+1} failed: {result}")

    # Update context if available
    if ctx and ctx.context and hasattr(ctx.context, 'legal_evidence'):
        ctx.context.legal_evidence.extend(all_evidence)
        logger.info(f"📝 Updated context with {len(all_evidence)} total evidence pieces")

    logger.info(f"🎯 Legal evidence search completed. Total evidence: {len(all_evidence)}")
    return all_evidence


def legal_evidence_search_agent_prompt(context_wrapper, agent) -> str:
    """Instructions for the legal evidence search agent."""
    return """
You are a Legal Evidence Search Agent specialized in finding regulatory and compliance requirements.

Your task is to search for legal evidence based on provided RetrievalNeed objects and return relevant Evidence.

**Instructions:**
- Take a list of RetrievalNeed objects as input
- Each RetrievalNeed contains:
  - query: The search query for legal requirements
  - must_tags: Required classification tags that must be present
  - nice_to_have_tags: Preferred tags that add context
- Use the `multi_legal_evidence_search` tool to find relevant legal evidence
- The tool will return Evidence objects containing:
  - kind: "web" (indicating web-sourced evidence)
  - ref: URL of the source
  - snippet: Relevant legal text excerpt

**Example:**
For RetrievalNeeds about "Utah curfew restrictions" and "age verification requirements", 
call: `multi_legal_evidence_search(retrieval_needs=[need1, need2])`

**Output:**
Return the list of Evidence objects directly as your final output. Each Evidence object represents 
a cited legal requirement or regulation relevant to the original queries.

Focus on:
- Federal, state, and local regulations
- Compliance requirements
- Legal precedents
- Statutory requirements
- Regulatory guidance

Ensure all evidence is properly cited with source URLs for verification.
"""


def create_legal_evidence_search_agent():
    """Create the Legal Evidence Search Agent with parallel search capability."""
    return Agent(
        name="Legal Evidence Search Agent",
        instructions=legal_evidence_search_agent_prompt,
        tools=[multi_legal_evidence_search],
        output_type=List[Evidence],
        model="gpt-5-nano",
    )