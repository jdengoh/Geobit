
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
from app.agent.analysis_agent import Evidence, RetrievalNeed
from dotenv import load_dotenv
from pydantic import BaseModel
from app.agent.schemas.agents import StateContext
from app.agent.evidence_web_search_agent import create_legal_evidence_search_agent

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
# -------------------- Mock Knowledge Base --------------------
# In production, this would connect to your actual KB/document system
# MOCK_KB_DOCS = {

# }


# -------------------- Search Tools --------------------
# @function_tool
# def kb_search(query: str, must_tags: List[str] = None, nice_tags: List[str] = None, max_results: int = 3) -> List[Dict[str, Any]]:
#     """
#     Search KB documents and return matching results.
#     """
#     must_tags = set(must_tags or [])
#     nice_tags = set(nice_tags or [])
#     results = []
    
#     for doc_id, doc in MOCK_KB_DOCS.items():
#         # Hard filter: document must have ALL must_tags
#         doc_tags = set(doc.get("tags", []))
#         if must_tags and not must_tags.issubset(doc_tags):
#             continue
        
#         # Relevance scoring (simple keyword + tag matching)
#         query_lower = query.lower()
#         content_lower = doc["content"].lower()
#         title_lower = doc["title"].lower()
        
#         score = 0
#         # Keyword matching
#         if query_lower in content_lower:
#             score += 2
#         if query_lower in title_lower:
#             score += 3
#         # Tag bonuses
#         score += len(nice_tags.intersection(doc_tags))
        
#         if score > 0:
#             results.append({
#                 "doc_id": doc_id,
#                 "title": doc["title"],
#                 "content": doc["content"],
#                 "score": score,
#                 "tags": doc["tags"]
#             })
    
#     # Sort by score and limit results
#     results.sort(key=lambda x: x["score"], reverse=True)
#     return results[:max_results]

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
    web_search_agent = create_legal_evidence_search_agent()
    web_search_tool = web_search_agent.as_tool(
        tool_name="web_search_agent",
        tool_description="Searches for and summarizes a list of jargon terms. Input a list of strings.",
    )
    return Agent[StateContext](
        name="Retrieval Agent (Rex)",
        instructions=retrieval_prompt,
        tools=[web_search_tool],
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



# -------------------- Demo/Test Function --------------------
# async def demo_retrieval():
#     """Demo the retrieval agent with sample retrieval needs."""
    
#     # Sample retrieval needs from the planner
#     sample_needs = [
#         RetrievalNeed(
#             query="Utah state-law guidance on age gating and login restrictions for minors; legal basis for curfew-based digital access controls",
#             must_tags=['child_safety', 'age_gating', 'personalization', 'jurisdiction_ut'],
#             nice_to_have_tags=['analytics_only', 'state_law', 'traceability', 'audit_logging']
#         ),
#         RetrievalNeed(
#             query="Legal and regulatory considerations for geofenced access controls inside Utah: privacy expectations, consent, and compliance within state borders",
#             must_tags=['child_safety', 'age_gating', 'personalization', 'jurisdiction_ut'],
#             nice_to_have_tags=['geo_enforcement', 'state_law', 'audit_logging', 'traceability']
#         ),
#         RetrievalNeed(
#             query="Best practices for auditing and logging during silent/shadow rollouts of minor-restriction features in Utah",
#             must_tags=['child_safety', 'age_gating', 'personalization', 'jurisdiction_ut'],
#             nice_to_have_tags=['silent_rollout', 'audit_logging', 'analytics_only', 'curfew', 'login_restriction', 'minor_protection']
#         )
#     ]
    
#     ctx = StateContext(session_id="demo-retrieval-001", current_agent="retrieval")
#     retrieval_agent = create_retrieval_agent()
    
#     print("=== RETRIEVAL DEMO ===")
#     print(f"Processing {len(sample_needs)} retrieval needs...")
    
#     evidence_list = await run_retrieval_agent(retrieval_agent, sample_needs, ctx)
    
#     print(f"\n=== RETRIEVED EVIDENCE ({len(evidence_list)} items) ===")
#     for i, evidence in enumerate(evidence_list, 1):
#         print(f"{i}. [{evidence.kind.upper()}] {evidence.ref}")
#         print(f"   Snippet: {evidence.snippet}")
#         print()
    
#     return evidence_list


# if __name__ == "__main__":
#     # Run the demo
#     asyncio.run(demo_retrieval())