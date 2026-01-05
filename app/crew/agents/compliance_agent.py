"""
ComplianceAgent - PII Redaction and Content Flagging
Fourth agent in the RAG pipeline
"""
from crewai import Agent
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

settings = get_settings()


def create_compliance_agent() -> Agent:
    """
    Create the ComplianceAgent.
    
    Responsibilities:
    - Scan analysis for PII (SSNs, credit cards, etc.)
    - Redact sensitive information if configured
    - Flag compliance concerns
    - Identify sensitive content
    - Ensure answer traceability
    - Document compliance actions taken
    
    Returns:
        CrewAI Agent configured for compliance
    """
    
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.0,  # Deterministic for compliance
        api_key=settings.OPENAI_API_KEY
    )
    
    return Agent(
        role="Compliance and Security Officer",
        goal=(
            "Review email analysis for sensitive information and compliance risks. "
            "Detect PII, confidential data, and sensitive content. Redact or flag "
            "as appropriate based on configuration. Ensure all responses are "
            "traceable to source documents."
        ),
        backstory=(
            "You are a compliance officer with expertise in data privacy regulations "
            "(GDPR, HIPAA, SOC 2). Your job is to protect sensitive information and "
            "ensure regulatory compliance. You can identify: "
            "1) PII: Social Security Numbers, credit card numbers, passport numbers, "
            "driver's license numbers, dates of birth with other identifiers. "
            "2) Confidential information: trade secrets, internal financial data, "
            "unreleased product information. "
            "3) Sensitive content: HR issues, legal matters, executive communications. "
            "When PII redaction is enabled, you replace sensitive data with "
            "[REDACTED-<type>] (e.g., [REDACTED-SSN], [REDACTED-CREDIT_CARD]). "
            "You always document what actions you took and why. You ensure that "
            "every statement in the final answer can be traced back to specific emails. "
            "You flag content that requires special handling or cannot be shown to "
            "the user. You fail closed - if unsure, you flag for review."
        ),
        llm=llm,
        verbose=settings.CREWAI_VERBOSE,
        allow_delegation=False,
        max_iter=2,
    )
