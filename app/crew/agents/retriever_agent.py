"""
RetrieverAgent - Queries Pinecone and Returns Ranked Chunks
First agent in the RAG pipeline
"""
from typing import List, Dict, Any
from crewai import Agent
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings

settings = get_settings()


def create_retriever_agent() -> Agent:
    """
    Create the RetrieverAgent.
    
    Responsibilities:
    - Query Pinecone vector database
    - Apply metadata filters (tenant, date, sender)
    - Rank results by relevance score
    - Return top-k chunks with metadata
    
    Returns:
        CrewAI Agent configured for retrieval
    """
    
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        temperature=0.0,  # Deterministic for retrieval
        google_api_key=settings.GEMINI_API_KEY
    )
    
    return Agent(
        role="Email Retrieval Specialist",
        goal=(
            "Query the vector database efficiently and retrieve the most relevant "
            "email chunks based on the user's query and filters. Ensure tenant "
            "isolation and return ranked results with full metadata."
        ),
        backstory=(
            "You are an expert at semantic search and information retrieval. "
            "You understand how to query vector databases effectively and apply "
            "metadata filters to narrow down results. You always verify tenant "
            "isolation and never mix data across organizations or users. "
            "You rank results by relevance score and include all necessary "
            "metadata for downstream agents."
        ),
        llm=llm,
        verbose=settings.CREWAI_VERBOSE,
        allow_delegation=False,  # Retriever works independently
        max_iter=1,  # Single retrieval operation
    )
