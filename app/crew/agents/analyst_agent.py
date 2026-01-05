"""
AnalystAgent - Performs Reasoning and Summarization
Third agent in the RAG pipeline
"""
from crewai import Agent
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

settings = get_settings()


def create_analyst_agent() -> Agent:
    """
    Create the AnalystAgent.
    
    Responsibilities:
    - Analyze reconstructed email context
    - Identify key themes, decisions, and action items
    - Detect agreements and disagreements
    - Flag risks or important issues
    - Summarize findings clearly
    - Maintain traceability to source emails
    
    Returns:
        CrewAI Agent configured for analysis
    """
    
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.2,  # Slight creativity for analysis
        api_key=settings.OPENAI_API_KEY
    )
    
    return Agent(
        role="Email Intelligence Analyst",
        goal=(
            "Analyze email conversations to extract insights, identify decisions, "
            "detect agreements or disagreements, flag risks, and provide clear "
            "summaries. Always ground analysis in the actual email content."
        ),
        backstory=(
            "You are a senior business analyst with expertise in email intelligence. "
            "You can read between the lines of email conversations to identify "
            "what's really being communicated. You detect decisions that were made, "
            "commitments that were given, concerns that were raised, and risks that "
            "were identified. You understand context and nuance. You can identify: "
            "1) Key decisions and who made them, "
            "2) Action items and ownership, "
            "3) Agreements and disagreements, "
            "4) Timeline commitments, "
            "5) Risks and blockers, "
            "6) Open questions. "
            "You ALWAYS cite specific emails when making claims. You NEVER "
            "hallucinate - if information isn't in the emails, you say so clearly."
        ),
        llm=llm,
        verbose=settings.CREWAI_VERBOSE,
        allow_delegation=False,
        max_iter=3,
    )
