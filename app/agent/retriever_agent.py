
"""
Retrieval Agent for Compliance Analysis System

The Retrieval Agent:
1. Takes AnalysisPlan.retrieval_needs (List[RetrievalNeed])
2. Searches KB documents and web sources
3. Applies must_tags as hard filters and nice_to_have_tags for ranking
4. Returns List[Evidence] with cited snippets
"""

import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set

from agents import Agent, RunContextWrapper, Runner, Tool, function_tool
from analysis_agent_alvin import Evidence, RetrievalNeed
from dotenv import load_dotenv
from pydantic import BaseModel
from schemas.agents import StateContext
from web_search_agent import create_web_search_agent_retriever

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
# -------------------- Mock Knowledge Base --------------------
# In production, this would connect to your actual KB/document system
MOCK_KB_DOCS = {
    "utah_social_media_act": {
        "title": "Utah Social Media Regulation Act",
        "content": "Utah Social Media Regulation Act requires parental consent and protections for minors, effective Mar 1, 2024. The act mandates age verification for users under 18 and requires platforms to implement curfew restrictions between 10:30 PM and 6:30 AM for minors without parental override.",
        "tags": ["jurisdiction_ut", "state_law", "minor_protection", "child_safety", "age_gating", "curfew"]
    },
    "utah_curfew_guidance": {
        "title": "Utah Minor Curfew Implementation Guidelines",
        "content": "Curfew-based restrictions for minors must be enforced by age verification and jurisdictional targeting in Utah. Platforms must log all curfew-related actions for compliance auditing. Geographic enforcement should be precise to Utah boundaries only.",
        "tags": ["curfew", "jurisdiction_ut", "minor_protection", "audit_logging", "geo_enforcement"]
    },
    "coppa_compliance": {
        "title": "COPPA Compliance Guidelines",
        "content": "Children's Online Privacy Protection Act requires verifiable parental consent for children under 13. Platforms must implement data minimization, provide clear privacy notices, and allow parents to review and delete their child's information.",
        "tags": ["child_safety", "age_gating", "federal_law", "privacy", "parental_consent"]
    },
    "personalization_minor_rules": {
        "title": "Personalization for Minors - Legal Framework",
        "content": "Personalized content and recommendations for users under 18 require special consideration under various state laws. Default settings should prioritize safety over engagement. Algorithmic recommendations must be auditable and transparent.",
        "tags": ["personalization", "minor_protection", "recommendation", "algorithm_transparency"]
    },
    "geo_enforcement_best_practices": {
        "title": "Geographic Enforcement Best Practices",
        "content": "Accurate geolocation is essential for jurisdiction-specific compliance. IP-based detection should be supplemented with additional signals. Cross-border users require careful handling to avoid over-enforcement.",
        "tags": ["geo_enforcement", "jurisdiction", "technical_implementation"]
    }
}

# Mock web sources (in production, this would use real web search APIs)
MOCK_WEB_SOURCES = [
    {
        "url": "https://ftc.gov/child-privacy",
        "title": "FTC Child Privacy Guidelines",
        "content": "FTC guidance emphasizes parental consent, age verification, data minimization for personalized or restricted experiences. Platforms should implement privacy-by-design principles for minor users.",
        "tags": ["child_safety", "federal_guidance", "privacy", "age_verification"]
    },
    {
        "url": "https://cdt.org/insights/state-social-media-laws-2024",
        "title": "State Social Media Laws Analysis 2024",
        "content": "Multiple states including Utah, Texas, and California have enacted social media regulations for minors. Common requirements include age verification, parental controls, and time-based restrictions.",
        "tags": ["state_law", "minor_protection", "age_verification", "jurisdiction"]
    },
    {
        "url": "https://nist.gov/privacy-framework/children-privacy",
        "title": "NIST Privacy Framework for Children",
        "content": "NIST recommends multi-layered age verification, granular parental controls, and comprehensive audit logging for children's online services. Technical safeguards should be the default, not opt-in.",
        "tags": ["age_verification", "audit_logging", "technical_standards", "child_safety"]
    }
]


# -------------------- Search Tools --------------------
@function_tool
def kb_search(query: str, must_tags: List[str] = None, nice_tags: List[str] = None, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Search KB documents and return matching results.
    """
    must_tags = set(must_tags or [])
    nice_tags = set(nice_tags or [])
    results = []
    
    for doc_id, doc in MOCK_KB_DOCS.items():
        # Hard filter: document must have ALL must_tags
        doc_tags = set(doc.get("tags", []))
        if must_tags and not must_tags.issubset(doc_tags):
            continue
        
        # Relevance scoring (simple keyword + tag matching)
        query_lower = query.lower()
        content_lower = doc["content"].lower()
        title_lower = doc["title"].lower()
        
        score = 0
        # Keyword matching
        if query_lower in content_lower:
            score += 2
        if query_lower in title_lower:
            score += 3
        # Tag bonuses
        score += len(nice_tags.intersection(doc_tags))
        
        if score > 0:
            results.append({
                "doc_id": doc_id,
                "title": doc["title"],
                "content": doc["content"],
                "score": score,
                "tags": doc["tags"]
            })
    
    # Sort by score and limit results
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def web_search_tool() -> Tool:
    """Search web sources for relevant information."""
    
    def web_search(query: str, must_tags: List[str] = None, nice_tags: List[str] = None, max_results: int = 2) -> List[Dict[str, Any]]:
        """
        Search web sources and return matching results.
        In production, this would call actual web search APIs.
        """
        must_tags = set(must_tags or [])
        nice_tags = set(nice_tags or [])
        results = []
        
        for source in MOCK_WEB_SOURCES:
            # Hard filter: source must have ALL must_tags
            source_tags = set(source.get("tags", []))
            if must_tags and not must_tags.issubset(source_tags):
                continue
            
            # Relevance scoring
            query_lower = query.lower()
            content_lower = source["content"].lower()
            title_lower = source["title"].lower()
            
            score = 0
            if query_lower in content_lower:
                score += 2
            if query_lower in title_lower:
                score += 3
            score += len(nice_tags.intersection(source_tags))
            
            if score > 0:
                results.append({
                    "url": source["url"],
                    "title": source["title"],
                    "content": source["content"],
                    "score": score,
                    "tags": source["tags"]
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    return Tool(
        name="web_search",
        description="Search web sources for relevant information",
        function=web_search,
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "must_tags": {"type": "array", "items": {"type": "string"}, "description": "Required tags"},
            "nice_tags": {"type": "array", "items": {"type": "string"}, "description": "Preferred tags"},
            "max_results": {"type": "integer", "default": 2, "description": "Maximum results"}
        }
    )


# -------------------- Retrieval Agent --------------------
def retrieval_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return """
You are a Compliance Retrieval Agent.

RETRIEVAL_NEEDS: {{retrieval_needs_json}}

For each RetrievalNeed:
1. Use kb_search for internal documents (pass must_tags and nice_to_have_tags)
2. Use web_search for external sources (pass must_tags and nice_to_have_tags)
3. Extract relevant snippets from results
4. Create Evidence objects with proper citations

Return JSON array of Evidence objects:
[
  {
    "kind": "doc",
    "ref": "doc:document_id#relevantSection",
    "snippet": "Short relevant excerpt from the document..."
  },
  {
    "kind": "web", 
    "ref": "https://example.com/page",
    "snippet": "Short relevant excerpt from web source..."
  }
]

Rules:
- Use BOTH kb_search AND web_search for comprehensive coverage
- Respect must_tags as hard filters - only return sources that have ALL must_tags
- Use nice_to_have_tags for ranking/preference
- Keep snippets focused (1-2 sentences max)
- Include diverse sources when possible
- Return ONLY the JSON array, no extra text
""".strip()


def create_retrieval_agent() -> Agent[StateContext]:
    web_search_agent = create_web_search_agent_retriever()
    web_search_tool = web_search_agent.as_tool(
        tool_name="web_search_agent",
        tool_description="Searches for and summarizes a list of jargon terms. Input a list of strings.",
    )
    return Agent[StateContext](
        name="Retrieval Agent (Rex)",
        instructions=retrieval_prompt,
        tools=[kb_search, web_search_tool],
        output_type=List[Evidence],
        model="gpt-5-nano",
    )


# -------------------- Runner Function --------------------
async def run_retrieval_agent(
    retrieval_agent: Agent[StateContext], 
    retrieval_needs: List[RetrievalNeed],
    ctx: StateContext
) -> List[Evidence]:
    """
    Run the retrieval agent with a list of RetrievalNeed objects.
    Returns a list of Evidence objects.
    """
    needs_json = json.dumps([need.model_dump() for need in retrieval_needs], indent=2)
    prompt = retrieval_prompt(None, None).replace(
        "{{retrieval_needs_json}}", needs_json
    )
    
    result = await Runner.run(retrieval_agent, prompt, context=ctx)
    
    # Store evidence in context for downstream use
    ctx.retrieved_evidence = result.final_output
    return result.final_output


# # -------------------- Integration Helper --------------------
# def evidence_from_search_results(kb_results: List[Dict], web_results: List[Dict]) -> List[Evidence]:
#     """
#     Helper function to convert search results to Evidence objects.
#     This can be used by the agent or as a fallback.
#     """
#     evidence = []
    
#     # Process KB results
#     for result in kb_results:
#         # Extract a relevant snippet (first 150 chars as example)
#         snippet = result["content"][:150] + "..." if len(result["content"]) > 150 else result["content"]
#         evidence.append(Evidence(
#             kind="doc",
#             ref=f"doc:{result['doc_id']}#content",
#             snippet=snippet
#         ))
    
#     # Process web results
#     for result in web_results:
#         snippet = result["content"][:150] + "..." if len(result["content"]) > 150 else result["content"]
#         evidence.append(Evidence(
#             kind="web",
#             ref=result["url"],
#             snippet=snippet
#         ))
    
#     return evidence


# -------------------- Demo/Test Function --------------------
async def demo_retrieval():
    """Demo the retrieval agent with sample retrieval needs."""
    
    # Sample retrieval needs from the planner
    sample_needs = [
        RetrievalNeed(
            query="Utah curfew restrictions for minors social media",
            must_tags=["jurisdiction_ut", "minor_protection"],
            nice_to_have_tags=["curfew", "child_safety"]
        ),
        RetrievalNeed(
            query="age verification requirements compliance",
            must_tags=["child_safety"],
            nice_to_have_tags=["age_gating", "federal_law"]
        ),
        RetrievalNeed(
            query="geographic enforcement jurisdictional boundaries",
            must_tags=[],
            nice_to_have_tags=["geo_enforcement", "jurisdiction"]
        )
    ]
    
    ctx = StateContext(session_id="demo-retrieval-001", current_agent="retrieval")
    retrieval_agent = create_retrieval_agent()
    
    print("=== RETRIEVAL DEMO ===")
    print(f"Processing {len(sample_needs)} retrieval needs...")
    
    evidence_list = await run_retrieval_agent(retrieval_agent, sample_needs, ctx)
    
    print(f"\n=== RETRIEVED EVIDENCE ({len(evidence_list)} items) ===")
    for i, evidence in enumerate(evidence_list, 1):
        print(f"{i}. [{evidence.kind.upper()}] {evidence.ref}")
        print(f"   Snippet: {evidence.snippet}")
        print()
    
    return evidence_list


if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_retrieval())