"""
ContextAgent - Reconstructs Email Threads Chronologically
Second agent in the RAG pipeline
"""
from crewai import Agent
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

settings = get_settings()


def create_context_agent() -> Agent:
    """
    Create the ContextAgent.
    
    Responsibilities:
    - Receive retrieved chunks from RetrieverAgent
    - Group chunks by email thread
    - Sort emails chronologically
    - Reconstruct full context of conversations
    - Maintain email metadata (sender, date, subject)
    
    Returns:
        CrewAI Agent configured for context building
    """
    
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.0,  # Deterministic for context assembly
        api_key=settings.OPENAI_API_KEY
    )
    
    return Agent(
        role="Email Context Reconstructor",
        goal=(
            "Reconstruct email conversations from retrieved chunks. "
            "Group related emails by thread, sort chronologically, and build "
            "a coherent narrative of the conversation. Maintain all metadata "
            "including sender, timestamp, and subject lines."
        ),
        backstory=(
            "You are an expert at understanding email conversations and threads. "
            "You can take fragmented email chunks and reconstruct the full "
            "conversation flow. You understand the importance of chronological "
            "ordering and context preservation. You know that the first email "
            "in a thread provides context for later replies. You always include "
            "sender information and timestamps to show who said what and when. "
            "You never invent information - you only work with what was retrieved."
        ),
        llm=llm,
        verbose=settings.CREWAI_VERBOSE,
        allow_delegation=False,
        max_iter=2,
    )
