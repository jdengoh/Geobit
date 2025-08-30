"""
Pre-Screening Agent (LLM-Only)

PURPOSE
-------
Evaluates feature descriptions to determine if they represent legitimate legal compliance 
measures or potentially problematic business decisions that could raise legal/ethical concerns.

Classifications:
  - "acceptable"           => ✅ Legitimate legal compliance measures
  - "problematic"          => ❌ Potentially discriminatory or ethically concerning
  - "needs_human_review"   => ❓ Ambiguous motivation, requires human evaluation

WHAT THIS CODE DOES (FLOW)
--------------------------
1) Send feature description to LLM for evaluation
2) LLM determines classification based on legal compliance vs problematic discrimination
3) Route appropriately:
   - acceptable: Continue to full compliance analysis pipeline
   - problematic: Flag for legal/ethics review and potential rejection
   - needs_human_review: Queue for human evaluation before proceeding

DECISION CRITERIA
-----------------
✅ ACCEPTABLE features:
  - Direct responses to specific legal requirements
  - Implemented to comply with named laws/regulations  
  - Designed to protect user rights or safety as mandated by law
  - Include specific jurisdictional legal references
  - Clear legal basis for any differential treatment

❌ PROBLEMATIC features:
  - Could enable discrimination without legal justification
  - Implemented for competitive advantage rather than compliance
  - Lack clear legal basis for differential treatment
  - Geographic restrictions that could unfairly disadvantage users
  - Business decisions disguised as compliance measures

❓ NEEDS_HUMAN_REVIEW features:
  - Ambiguous about their motivation
  - Missing context about the underlying legal reason
  - Could be either legitimate compliance or problematic discrimination
  - Unclear whether geographic restrictions serve user protection
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Literal, Optional

from agents import Agent, RunContextWrapper, Runner
from dotenv import load_dotenv

from app.agent.schemas.agents import StateContext

# ----------------- Schemas -----------------
@dataclass
class PreScreeningResult:
    classification: Literal["acceptable", "problematic", "needs_human_review"]
    reasoning: str
    legal_requirement_found: bool
    legal_references: List[str]
    user_protection_basis: Optional[str]
    discrimination_risk: str  # "none", "low", "medium", "high"
    recommended_action: str

# ----------------- LLM Prompt -----------------
def prescreening_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return """
You are evaluating feature descriptions to determine if they represent legitimate legal compliance measures or potentially problematic business decisions that could raise legal/ethical concerns.

FEATURE_NAME: {{feature_name}}
FEATURE_DESCRIPTION: {{feature_description}}
JARGON_JSON: {{jargon_json}}

Your task is to classify the feature into one of three categories:

ACCEPTABLE: Features that are:
- Direct responses to specific legal requirements
- Implemented to comply with named laws/regulations
- Designed to protect user rights or safety as mandated by law
- Include specific jurisdictional legal references

PROBLEMATIC: Features that are:
- Implemented primarily for competitive advantage rather than compliance
- Lack clear legal basis for differential treatment
- Feature DOES NOT affect user rights and user security
- Geographic restrictions that could unfairly disadvantage users
- Clearly motivated by business strategy rather than legal requirements

NEEDS_HUMAN_REVIEW: Features that are:
- Ambiguous about their motivation
- Missing context about the underlying legal reason
- Unclear whether geographic restrictions serve user protection and/or meeting user guidelines
- Have some legal elements but unclear if they're the primary driver

For your evaluation, consider:
1. Is there a specific legal requirement, regulation, or law mentioned?
2. Does the feature serve user protection purposes mandated by law?
3. Is the business rationale clearly secondary to legal compliance?
4. Does the feature possibly affect user rights and user security?
5. Are there specific legal citations or jurisdictional references?

Return STRICT JSON:
{
  "classification": "acceptable" | "problematic" | "needs_human_review",
  "reasoning": "Detailed explanation of your classification decision, referencing specific aspects of the feature description",
}

Focus on distinguishing legitimate legal compliance from potentially discriminatory business decisions. Look for specific legal citations, clear user protection rationale, and evidence of legal mandate rather than business preference.
""".strip()

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

def create_llm_prescreener() -> Agent[StateContext]:
    return Agent[StateContext](
        name="Pre-Screening Agent",
        instructions=prescreening_prompt,
        tools=[],
        output_type=PreScreeningResult,
        model="gpt-5-nano",
    )

def _dump_jargon_for_prompt(jargon: object) -> str:
    """
    Normalizes JargonQueryResult (Pydantic) or dict to a stable JSON string.
    """
    if jargon is None:
        return "{}"
    if hasattr(jargon, "model_dump"):
        return json.dumps(jargon.model_dump(), sort_keys=True)
    if isinstance(jargon, dict):
        return json.dumps(jargon, sort_keys=True)
    return "{}"

async def run_prescreening(ctx: StateContext) -> PreScreeningResult:
    """
    Main entry point for pre-screening evaluation.
    """
    if not ctx.feature_description:
        raise ValueError("Pre-screening requires feature_description in context")
    
    feature_name = getattr(ctx, 'feature_name', '') or ""
    feature_desc = ctx.feature_description
    
    # Prepare jargon context
    jr_json = _dump_jargon_for_prompt(ctx.jargon_translation)

    # Run LLM analysis
    agent = create_llm_prescreener()
    prompt = (prescreening_prompt(None, None)
                .replace("{{feature_name}}", feature_name)
                .replace("{{feature_description}}", feature_desc)
                .replace("{{jargon_json}}", jr_json))
    
    res = await Runner.run(agent, prompt, context=ctx)
    result = res.final_output
    
    # Set recommended actions based on classification
    if result.classification == "acceptable":
        result.recommended_action = "Proceed to full compliance analysis pipeline"
    elif result.classification == "problematic":
        result.recommended_action = "Flag for legal/ethics review - potential discrimination risk"
    else:  # needs_human_review
        result.recommended_action = "Queue for human evaluation to clarify legal vs business motivation"
    
    # Store result in context for downstream agents
    ctx.prescreening_result = result
    
    return result

# ----------------- Integration Helpers -----------------
def is_acceptable_for_compliance_analysis(result: PreScreeningResult) -> bool:
    """
    Determine if feature is acceptable and should proceed to compliance analysis.
    """
    return result.classification == "acceptable"

def requires_legal_ethics_review(result: PreScreeningResult) -> bool:
    """
    Determine if feature should be flagged for legal/ethics review due to discrimination risk.
    """
    return (result.classification == "problematic" or 
            result.discrimination_risk in ["high", "medium"])

def requires_human_evaluation(result: PreScreeningResult) -> bool:
    """
    Determine if human evaluation is needed to clarify motivation.
    """
    return result.classification == "needs_human_review"

# ----------------- Demo -----------------
if __name__ == "__main__":
    import asyncio

    # Test cases based on your original examples
    test_cases = [
        {
            "name": "Underage protection via Snowcap trigger",
            "desc": "Snowcap is activated for all underage users platform-wide, applying ASL to segment accounts. Actions taken under this logic are routed to CDS and monitored using BB to identify deviations in usage.",
            "expected": "needs_human_review"  # Ambiguous legal requirement
        },
        {
            "name": "Trial run of video replies in EU", 
            "desc": "Roll out video reply functionality to users in EEA only. GH will manage exposure control, and BB is used to baseline feedback.",
            "expected": "problematic"  # Business/testing driven
        },
        {
            "name": "Jellybean-based parental notifications for Florida regulation",
            "desc": "To support Florida's Online Protections for Minors law, this feature extends the Jellybean parental control framework. Notifications are dispatched to verified parent accounts when a minor attempts to access restricted features. Using IMT, the system checks behavioral anomalies against BB models. If violations are detected, restrictions are applied in ShadowMode with full audit logging through CDS. Glow flags ensure compliance visibility during rollout phases.",
            "expected": "acceptable"  # Clear legal compliance
        },
        {
            "name": "Korea Video Filter",
            "desc": "A video filter feature is available globally except KR", 
            "expected": "needs_human_review"  # Ambiguous - no clear rationale
        },
        
        
    ]
    
    async def test_prescreening():
        print("=== PRE-SCREENING AGENT TEST ===\n")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"{i}. Testing: {test_case['name']}")
            print(f"   Description: {test_case['desc']}")
            
            SAMPLE = {
                "detected_terms": [
                    {"term":"NR","definition":"Not recommended"},
                    {"term":"PF","definition":"Personalized feed"},
                    {"term":"GH","definition":"Geo-handler; a module responsible for routing features based on user region"},
                    {"term":"CDS","definition":"Compliance Detection System"},
                    {"term":"DRT","definition":"Data retention threshold; duration for which logs can be stored"},
                    {"term":"LCP","definition":"Local compliance policy"},
                    {"term":"Redline","definition":"Flag for legal review (different from its traditional business use for 'financial loss')"},
                    {"term":"Softblock","definition":"A user-level limitation applied silently without notifications"},
                    {"term":"Spanner","definition":"A synthetic name for a rule engine (not to be confused with Google Spanner)"},
                    {"term":"ShadowMode","definition":"Deploy feature in non-user-impact way to collect analytics only"},
                    {"term":"T5","definition":"Tier 5 sensitivity data; more critical than T1–T4 in this internal taxonomy"},
                    {"term":"ASL","definition":"Age-sensitive logic"},
                    {"term":"Glow","definition":"A compliance-flagging status, internally used to indicate geo-based alerts"},
                    {"term":"NSP","definition":"Non-shareable policy (content should not be shared externally)"},
                    {"term":"Jellybean","definition":"Feature name for internal parental control system"},
                    {"term":"EchoTrace","definition":"Log tracing mode to verify compliance routing"},
                    {"term":"BB","definition":"Baseline Behavior; standard user behavior used for anomaly detection"},
                    {"term":"Snowcap","definition":"A synthetic codename for the child safety policy framework"},
                    {"term":"FR","definition":"Feature rollout status"},
                    {"term":"IMT","definition":"Internal monitoring trigger"}
                ],
                "searched_terms": [
                    {"term":"Utah Social Media Regulation Act","definition":"state social media law","sources":[{"title":"Utah OAG","link":"https://oag.utah.gov"}]}
                ],
                "unknown_terms":[]
            }

            ctx = StateContext(
                session_id=f"test-{test_case['name'].lower().replace(' ', '-')}",
                current_agent="prescreener",
                feature_name=test_case['name'],
                feature_description=test_case['desc'],
                jargon_translation=SAMPLE,
            )
            
            result = await run_prescreening(ctx)
            
            print(f"   Classification: {result.classification}")
            print(f"   Expected: {test_case['expected']}")
            print(f"   Reasoning: {result.reasoning}")
            print(f"   Legal References: {result.legal_references}")
            print(f"   Discrimination Risk: {result.discrimination_risk}")
            
            # Validation
            correct = result.classification == test_case['expected']
            print(f"   Result: {'✅ CORRECT' if correct else '❌ INCORRECT'}")
            print()
    
    asyncio.run(test_prescreening())