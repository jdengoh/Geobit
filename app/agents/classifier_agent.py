# compliance_classifier.py
import enum

from agents import Agent
from pydantic import BaseModel


class Classification(str, enum.Enum):
    COMPLIANCE_REQUIRED = "COMPLIANCE_REQUIRED"
    NO_COMPLIANCE = "NO_COMPLIANCE"
    UNCLEAR_DUE_TO_JARGON = "UNCLEAR_DUE_TO_JARGON"
    UNCLEAR_NEEDS_HUMAN = "UNCLEAR_NEEDS_HUMAN"


class RoutingResult(BaseModel):
    classification: Classification
    """The routing decision for this feature"""

    reasoning: str
    """Why this routing decision was made"""


# CLASSIFICATION_INSTRUCTIONS = """
# You are a Compliance Classifier Agent for TikTok's geo-compliance detection system.

# TASK: Analyze feature descriptions and route them to the appropriate next step.

# ROUTING OPTIONS:
# - COMPLIANCE_REQUIRED: Feature mentions specific laws, regulations, or legal compliance requirements with geographic restrictions
# - NO_COMPLIANCE: Feature has geographic restrictions for business reasons (market testing, rollout strategy, business decisions)
# - UNCLEAR_DUE_TO_JARGON: Description contains heavy TikTok internal jargon that prevents clear analysis
# - UNCLEAR_NEEDS_HUMAN: Clear description but ambiguous intent about legal vs business motivation

# KEY INDICATORS FOR COMPLIANCE:
# - Phrases: "to comply with", "in line with", "regulatory requirement", "legal obligation"
# - Specific law names: "GDPR", "CCPA", "Utah Social Media Regulation Act", "SB976"
# - Legal contexts: age restrictions for minors, data protection, content moderation requirements

# KEY INDICATORS FOR NO_COMPLIANCE:
# - Phrases: "market testing", "business decision", "rollout strategy", "A/B testing"
# - Geographic restrictions without legal justification

# OUTPUT: Return only the routing classification and brief reasoning for the decision.
# """

CLASSIFICATION_INSTRUCTIONS = """
You are a Compliance Classifier Agent for TikTok's geo-compliance detection system.

TASK: Analyze feature descriptions, classify them, and create a plan for tool execution.

STEP 1 - CLASSIFICATION:
Determine the routing classification:

ROUTING OPTIONS:
- COMPLIANCE_REQUIRED: Feature mentions specific laws, regulations, or legal compliance requirements with geographic restrictions
- NO_COMPLIANCE: Feature has geographic restrictions for business reasons (market testing, rollout strategy, business decisions)
- UNCLEAR_DUE_TO_JARGON: Description contains heavy TikTok internal jargon that prevents clear analysis
- UNCLEAR_NEEDS_HUMAN: Clear description but ambiguous intent about legal vs business motivation

KEY INDICATORS FOR COMPLIANCE:
- Phrases: "to comply with", "in line with", "regulatory requirement", "legal obligation"
- Specific law names: "GDPR", "CCPA", "Utah Social Media Regulation Act", "SB976"
- Legal contexts: age restrictions for minors, data protection, content moderation requirements

KEY INDICATORS FOR NO_COMPLIANCE:
- Phrases: "market testing", "business decision", "rollout strategy", "A/B testing"
- Geographic restrictions without legal justification

STEP 2 - TOOL EXECUTION PLAN:
Based on your classification, create and execute a plan for tool calls:

FOR COMPLIANCE_REQUIRED:
1. Call analyze_regulations_tool to extract specific regulations
2. Call generate_compliance_report_tool with classification, reasoning, and regulations

FOR NO_COMPLIANCE:
1. Call generate_compliance_report_tool with classification and reasoning (no regulation analysis needed)

FOR UNCLEAR_DUE_TO_JARGON:
1. Call generate_compliance_report_tool flagging for context enrichment or human review

FOR UNCLEAR_NEEDS_HUMAN:
1. Call generate_compliance_report_tool flagging for human review

EXECUTION APPROACH:
- First, analyze and classify the feature
- State your classification and reasoning clearly
- Create your tool execution plan
- Execute the planned tool calls in sequence
- Ensure the final output is a comprehensive compliance report

AVAILABLE TOOLS:
- analyze_regulations_tool: Extract regulations from compliance-required features
- generate_compliance_report_tool: Generate final compliance report in markdown

OUTPUT: Execute your plan and provide the final compliance analysis report.
"""


def create_classifier_agent() -> Agent:
    return Agent(
        name="Classifier Agent",
        instructions=CLASSIFICATION_INSTRUCTIONS,
        model="gpt-5-nano",
        # output_type=RoutingResult,
    )
