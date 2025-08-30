"""
Pre-Screening Agent (LLM + Deterministic Rules)

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
1) Analyze feature description for legal compliance vs problematic discrimination signals
2) Use LLM to evaluate specific legal requirements, user protection, and business rationale
3) Apply deterministic rules to validate classification
4) Route appropriately:
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
import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from agents import Agent, RunContextWrapper, Runner
from dotenv import load_dotenv

from schemas.agents import StateContext

# ----------------- Config -----------------
CONFIDENCE_THRESHOLD = 0.75  # High confidence threshold for auto-routing

# Acceptable compliance indicators (strong legal basis)
STRONG_LEGAL_COMPLIANCE = {
    # Explicit legal requirements
    "mandated by", "required by law", "compliance with", "pursuant to", 
    "in accordance with", "to comply with", "legal requirement", "statutory obligation",
    "court order", "regulatory requirement", "legal mandate", "enforced by law",
    
    # Specific named laws/regulations
    "gdpr", "coppa", "ccpa", "cpra", "dsa", "dma", "privacy act", "data protection act",
    "accessibility act", "ada compliance", "child protection law", "social media act",
    "digital services act", "consumer protection", "anti-discrimination law",
    
    # User protection with legal basis  
    "user rights protection", "legally mandated safety", "required safeguards",
    "regulatory compliance", "consumer protection law", "minor protection law"
}

# Problematic discrimination indicators
PROBLEMATIC_INDICATORS = {
    # Competitive advantage language
    "competitive advantage", "market advantage", "business strategy", "market positioning",
    "revenue optimization", "profit maximization", "cost reduction", "efficiency gains",
    
    # Discriminatory potential
    "restrict access", "limit availability", "exclude users", "preferential treatment",
    "selective access", "tiered service", "premium features", "market segmentation",
    
    # Business rationale without legal basis
    "business decision", "corporate policy", "internal guidelines", "company preference",
    "operational efficiency", "resource allocation", "market testing", "pilot program"
}

# User protection indicators (could be acceptable if legally mandated)
USER_PROTECTION_SIGNALS = {
    "user safety", "child protection", "minor safety", "privacy protection", 
    "data protection", "user rights", "consumer protection", "safety measures",
    "harm prevention", "abuse prevention", "content moderation", "age verification"
}

# ----------------- Schemas -----------------
@dataclass
class PreScreeningResult:
    classification: Literal["acceptable", "problematic", "needs_human_review"]
    confidence: float
    reasoning: str
    legal_requirement_found: bool
    legal_references: List[str]
    user_protection_basis: Optional[str]
    business_rationale_secondary: bool
    discrimination_risk: str  # "none", "low", "medium", "high"
    recommended_action: str

# ----------------- Deterministic Analysis -----------------
def _analyze_legal_basis(text: str) -> Tuple[bool, List[str]]:
    """
    Identify if there are specific legal requirements mentioned.
    """
    text_lower = text.lower()
    legal_refs = []
    
    for indicator in STRONG_LEGAL_COMPLIANCE:
        if indicator in text_lower:
            legal_refs.append(indicator)
    
    # Look for specific law citations (pattern matching)
    law_patterns = [
        r'(gdpr|general data protection regulation)',
        r'(coppa|children.{0,20}online privacy)',
        r'(ccpa|california consumer privacy)', 
        r'(ada|americans with disabilities)',
        r'(section \d+)', r'(article \d+)', r'(regulation \d+)',
        r'(france.{0,30}copyright)', r'(eu.{0,20}digital services)',
        r'(utah.{0,20}social media)', r'(indonesia.{0,30}child protection)'
    ]
    
    for pattern in law_patterns:
        matches = re.findall(pattern, text_lower)
        legal_refs.extend(matches)
    
    has_legal_basis = len(legal_refs) > 0
    return has_legal_basis, legal_refs

def _assess_user_protection(text: str) -> Optional[str]:
    """
    Determine if geographic restrictions serve user protection purposes.
    """
    text_lower = text.lower()
    
    # Look for user protection context
    for signal in USER_PROTECTION_SIGNALS:
        if signal in text_lower:
            # Check if it's tied to legal requirements
            if any(legal in text_lower for legal in ["law", "regulation", "mandate", "require"]):
                return f"User protection via {signal} with legal basis"
            else:
                return f"User protection via {signal} (legal basis unclear)"
    
    # Check for harmful content protection
    harm_patterns = ['block.{0,20}harmful', 'prevent.{0,20}abuse', 'protect.{0,20}minor']
    for pattern in harm_patterns:
        if re.search(pattern, text_lower):
            return "Harm prevention measures"
    
    return None

def _evaluate_business_rationale(text: str) -> Tuple[bool, float]:
    """
    Assess if business rationale is clearly secondary to legal compliance.
    Returns (is_secondary, discrimination_risk_score)
    """
    text_lower = text.lower()
    
    business_signals = sum(1 for indicator in PROBLEMATIC_INDICATORS if indicator in text_lower)
    legal_signals = sum(1 for indicator in STRONG_LEGAL_COMPLIANCE if indicator in text_lower)
    
    # If strong legal signals and few business signals = secondary business rationale
    is_secondary = legal_signals > business_signals and legal_signals >= 2
    
    # Discrimination risk scoring
    risk_score = 0.0
    if "restrict" in text_lower or "exclude" in text_lower or "limit" in text_lower:
        risk_score += 0.3
    if business_signals > legal_signals:
        risk_score += 0.4
    if "competitive" in text_lower or "advantage" in text_lower:
        risk_score += 0.3
    if not any(legal in text_lower for legal in ["law", "regulation", "compliance"]):
        risk_score += 0.2
        
    return is_secondary, min(1.0, risk_score)

def _deterministic_classification(has_legal_basis: bool, legal_refs: List[str],
                                user_protection: Optional[str], is_business_secondary: bool,
                                discrimination_risk: float) -> Tuple[str, float]:
    """
    Apply deterministic rules for classification.
    """
    # Strong legal basis + user protection + secondary business = acceptable
    if has_legal_basis and len(legal_refs) >= 2 and user_protection and is_business_secondary:
        return "acceptable", 0.9
    
    # Clear legal requirement with specific references = acceptable
    if has_legal_basis and len(legal_refs) >= 1 and discrimination_risk <= 0.3:
        return "acceptable", 0.8
        
    # High discrimination risk without legal basis = problematic  
    if discrimination_risk >= 0.6 and not has_legal_basis:
        return "problematic", 0.85
        
    # Business-driven with discrimination potential = problematic
    if not is_business_secondary and discrimination_risk >= 0.4:
        return "problematic", 0.75
        
    # Some legal basis but unclear context = needs review
    if has_legal_basis and (not user_protection or discrimination_risk > 0.4):
        return "needs_human_review", 0.7
        
    # No clear legal basis but low discrimination risk = needs review
    if not has_legal_basis and discrimination_risk <= 0.4:
        return "needs_human_review", 0.6
        
    # Default: ambiguous cases need human review
    return "needs_human_review", 0.5

# ----------------- LLM Prompt -----------------
def prescreening_prompt(_: RunContextWrapper[StateContext], __: Agent[StateContext]) -> str:
    return """
You are evaluating feature descriptions to determine if they represent legitimate legal compliance measures or potentially problematic business decisions that could raise legal/ethical concerns.

FEATURE_NAME: {{feature_name}}
FEATURE_DESCRIPTION: {{feature_description}}
JARGON_JSON: {{jargon_json}}

ACCEPTABLE: Features that are:
- Direct responses to specific legal requirements
- Implemented to comply with named laws/regulations
- Designed to protect user rights or safety as mandated by law
- Include specific jurisdictional legal references

PROBLEMATIC: Features that are:
- Motivation for releasing feature is clear but not does not state which legal requirement it is trying to
- Feature motivation clearly has nothing to do with user protection or trying to meet any legal requirements
- Feature DEFINITELY does not affect user security and user rights

NEEDS_HUMAN_REVIEW: Features that are:
- Ambiguous about their motivation
- Missing context about the underlying reason
- Feature may or may not affect user security and user rights, but insufficient information about the feature is available from the description


For each description, identify:
1. Whether there's a specific legal requirement mentioned
2. If the geographic restriction serves user protection
3. Whether the business rationale is clearly secondary to legal compliance

Return STRICT JSON:
{
  "classification": "acceptable" | "problematic" | "needs_human_review",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentences explaining the classification based on the three criteria above",
}

Focus on distinguishing legitimate legal compliance from potentially discriminatory business decisions. Look for specific legal citations and clear user protection rationale.
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

# ----------------- Main Logic -----------------
def _align_with_deterministic_rules(llm_result: PreScreeningResult,
                                  has_legal_basis: bool, 
                                  legal_refs: List[str],
                                  user_protection: Optional[str],
                                  is_business_secondary: bool,
                                  discrimination_risk: float) -> PreScreeningResult:
    """
    Validate and adjust LLM classification using deterministic rules.
    """
    det_classification, det_confidence = _deterministic_classification(
        has_legal_basis, legal_refs, user_protection, is_business_secondary, discrimination_risk
    )
    
    # Override LLM if deterministic rules have high confidence and disagree
    if det_confidence >= CONFIDENCE_THRESHOLD and det_classification != llm_result.classification:
        llm_result.classification = det_classification
        llm_result.reasoning += f" [Adjusted by deterministic analysis of legal basis and discrimination risk.]"
    
    # Blend confidences (deterministic gets higher weight for clear cases)
    weight = 0.7 if det_confidence >= CONFIDENCE_THRESHOLD else 0.4
    llm_result.confidence = weight * det_confidence + (1 - weight) * llm_result.confidence
    
    # Ensure structured fields are populated from deterministic analysis
    llm_result.legal_requirement_found = has_legal_basis
    llm_result.legal_references = legal_refs if legal_refs else llm_result.legal_references
    llm_result.user_protection_basis = user_protection or llm_result.user_protection_basis
    llm_result.business_rationale_secondary = is_business_secondary
    
    # Map discrimination risk score to category
    if discrimination_risk >= 0.7:
        llm_result.discrimination_risk = "high"
    elif discrimination_risk >= 0.4:
        llm_result.discrimination_risk = "medium"  
    elif discrimination_risk >= 0.2:
        llm_result.discrimination_risk = "low"
    else:
        llm_result.discrimination_risk = "none"
    
    # Set recommended actions
    if llm_result.classification == "acceptable":
        llm_result.recommended_action = "Proceed to full compliance analysis pipeline"
    elif llm_result.classification == "problematic":
        llm_result.recommended_action = "Flag for legal/ethics review - potential discrimination risk"
    else:  # needs_human_review
        llm_result.recommended_action = "Queue for human evaluation to clarify legal vs business motivation"
    
    return llm_result
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
    full_text = f"{feature_name} {feature_desc}"
    
    # Deterministic analysis
    has_legal_basis, legal_refs = _analyze_legal_basis(full_text)
    user_protection = _assess_user_protection(full_text) 
    is_business_secondary, discrimination_risk = _evaluate_business_rationale(full_text)
    
    # LLM analysis
    jr_json = _dump_jargon_for_prompt(ctx.jargon_translation)

    agent = create_llm_prescreener()
    prompt = (prescreening_prompt(None, None)
                .replace("{{feature_name}}", feature_name)
                .replace("{{feature_description}}", feature_desc)
                .replace("{{jargon_json}}", jr_json))
    
    res = await Runner.run(agent, prompt, context=ctx)
    llm_result = res.final_output
    
    # Align with deterministic rules
    final_result = _align_with_deterministic_rules(
        llm_result, has_legal_basis, legal_refs, user_protection, 
        is_business_secondary, discrimination_risk
    )
    
    # Store result in context for downstream agents
    ctx.prescreening_result = final_result
    
    return final_result

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
    return (result.classification == "needs_human_review" or 
            result.confidence < 0.6)

# ----------------- Demo -----------------
if __name__ == "__main__":
    import asyncio

    # Test cases based on your original examples
    test_cases = [
        {
            "name": "Underage protection via Snowcap trigger",
            "desc": "Snowcap is activated for all underage users platform-wide, applying ASL to segment accounts. Actions taken under this logic are routed to CDS and monitored using BB to identify deviations in usage.",
            "expected": "problematic"  # Lacking Clear legal requirement
        },
        {
            "name": "Trial run of video replies in EU", 
            "desc": "Roll out video reply functionality to users in EEA only. GH will manage exposure control, and BB is used to baseline feedback.",
            "expected": "problematic"  # Business or testing driven
        },
        {
            "name": "Jellybean-based parental notifications for Florida regulation",
            "desc": "To support Florida's Online Protections for Minors law, this feature extends the Jellybean parental control framework. Notifications are dispatched to verified parent accounts when a minor attempts to access restricted features. Using IMT, the system checks behavioral anomalies against BB models. If violations are detected, restrictions are applied in ShadowMode with full audit logging through CDS. Glow flags ensure compliance visibility during rollout phases.",
            "expected": "acceptable"  # Business-driven, potential discrimination
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
            
            SAMPLE =  {
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
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Reasoning: {result.reasoning}")
            
            # Validation
            correct = result.classification == test_case['expected']
            print(f"   Result: {'✅ CORRECT' if correct else '❌ INCORRECT'}")
            print()
    
    asyncio.run(test_prescreening())