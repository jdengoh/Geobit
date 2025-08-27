# analysis_agent.py
import enum
from pydantic import BaseModel
from agents import Agent

class ComplianceDomain(str, enum.Enum):
    PRIVACY = "privacy"
    MINOR_PROTECTION = "minor_protection" 
    CONTENT_REGULATION = "content_regulation"
    DATA_LOCALIZATION = "data_localization"
    CHILD_SAFETY = "child_safety"
    FINANCIAL = "financial"
    OTHER = "other"

class RegulationInfo(BaseModel):
    name: str
    """Name of the regulation (exact or descriptive)"""
    
    jurisdiction: str
    """Geographic scope (Utah, California, European Union, etc.)"""
    
    domain: ComplianceDomain
    """Primary compliance domain"""

class AnalysisResult(BaseModel):
    regulations_found: list[RegulationInfo] = []
    """List of regulations identified in the feature"""
    
    summary: str = ""
    """Brief summary of compliance requirements"""
    
    jurisdictions: list[str] = []
    """All jurisdictions mentioned"""

ANALYSIS_AGENT_INSTRUCTIONS = """
You are an Analysis Agent for TikTok's geo-compliance detection system.

TASK: Extract and structure regulation information from features already classified as requiring compliance.

EXTRACTION TARGETS:
- Specific law names: "Utah Social Media Regulation Act", "California SB976", "GDPR"
- Implied regulations: "US federal law requiring NCMEC reporting" → "Federal CSAM Reporting Requirements"
- Jurisdictions: Utah, California, European Union, United States, etc.
- Compliance domains: What type of legal requirement is this?

REGULATION MAPPING:
- Utah Social Media Regulation Act → minor_protection, Utah
- California SB976 → minor_protection, California  
- GDPR → privacy, European Union
- CCPA → privacy, California
- Federal CSAM/NCMEC requirements → child_safety, United States

JURISDICTION STANDARDIZATION:
- Utah → "Utah"
- California → "California" 
- EU/European → "European Union"
- US/Federal → "United States"
- Country codes → Full country names

DOMAIN CLASSIFICATION:
- PRIVACY: Data protection, user privacy, data handling
- MINOR_PROTECTION: Age restrictions, parental controls, youth safety
- CHILD_SAFETY: CSAM reporting, child abuse prevention
- CONTENT_REGULATION: Copyright, content moderation, censorship
- DATA_LOCALIZATION: Data residency, cross-border restrictions
- FINANCIAL: Payment processing, financial data handling

OUTPUT: Extract all regulations mentioned and provide structured information with jurisdiction and domain classification.
"""

def create_analysis_agent() -> Agent:
    return Agent(
        name="Analysis Agent",
        instructions=ANALYSIS_AGENT_INSTRUCTIONS,
        model="gpt-5-nano",
        output_type=AnalysisResult,
    )
