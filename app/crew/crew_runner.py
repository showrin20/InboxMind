"""
Crew Runner - Orchestrates Sequential RAG Pipeline
Coordinates all 5 agents in strict order: Retrieve → Context → Analyze → Compliance → Answer
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from crewai import Crew, Process
import json

from app.crew.agents.retriever_agent import create_retriever_agent
from app.crew.agents.context_agent import create_context_agent
from app.crew.agents.analyst_agent import create_analyst_agent
from app.crew.agents.compliance_agent import create_compliance_agent
from app.crew.agents.answer_agent import create_answer_agent

from app.crew.tasks.crew_tasks import (
    create_retrieval_task,
    create_context_task,
    create_analysis_task,
    create_compliance_task,
    create_answer_task
)

from app.core.config import get_settings
from app.core.logging import performance_logger

settings = get_settings()
logger = logging.getLogger(__name__)


class RAGCrew:
    """
    Orchestrates the RAG pipeline using CrewAI.
    Enforces sequential execution: no agent may skip steps.
    """
    
    def __init__(self):
        """Initialize agents (reusable across queries)"""
        logger.info("Initializing RAG Crew agents...")
        
        self.retriever_agent = create_retriever_agent()
        self.context_agent = create_context_agent()
        self.analyst_agent = create_analyst_agent()
        self.compliance_agent = create_compliance_agent()
        self.answer_agent = create_answer_agent()
        
        logger.info("RAG Crew agents initialized")
    
    async def run_rag_pipeline(
        self,
        user_query: str,
        retrieved_chunks: List[Dict[str, Any]],
        org_id: str,
        user_id: str,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Execute the complete RAG pipeline.
        
        Args:
            user_query: User's query string
            retrieved_chunks: Results from Pinecone vector search
            org_id: Organization ID for audit logging
            user_id: User ID for audit logging
            request_id: Request tracing ID
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        start_time = datetime.now()
        
        logger.info(
            f"Starting RAG pipeline for request_id={request_id}, "
            f"query={user_query[:100]}, chunks={len(retrieved_chunks)}"
        )
        
        try:
            # Task 1: Process retrieved chunks
            retrieval_start = datetime.now()
            retrieval_task = create_retrieval_task(
                query=user_query,
                retrieved_chunks=retrieved_chunks,
                agent=self.retriever_agent
            )
            retrieval_duration = (datetime.now() - retrieval_start).total_seconds() * 1000
            
            # Task 2: Reconstruct context
            context_start = datetime.now()
            context_task = create_context_task(agent=self.context_agent)
            context_task.context = [retrieval_task]
            context_duration = (datetime.now() - context_start).total_seconds() * 1000
            
            # Task 3: Analyze emails
            analysis_start = datetime.now()
            analysis_task = create_analysis_task(
                user_query=user_query,
                agent=self.analyst_agent
            )
            analysis_task.context = [retrieval_task, context_task]
            analysis_duration = (datetime.now() - analysis_start).total_seconds() * 1000
            
            # Task 4: Compliance review
            compliance_start = datetime.now()
            compliance_task = create_compliance_task(agent=self.compliance_agent)
            compliance_task.context = [analysis_task]
            compliance_duration = (datetime.now() - compliance_start).total_seconds() * 1000
            
            # Task 5: Generate answer
            answer_start = datetime.now()
            answer_task = create_answer_task(
                user_query=user_query,
                agent=self.answer_agent
            )
            answer_task.context = [compliance_task]
            answer_duration = (datetime.now() - answer_start).total_seconds() * 1000
            
            # Create crew with sequential process (ENFORCED)
            crew = Crew(
                agents=[
                    self.retriever_agent,
                    self.context_agent,
                    self.analyst_agent,
                    self.compliance_agent,
                    self.answer_agent
                ],
                tasks=[
                    retrieval_task,
                    context_task,
                    analysis_task,
                    compliance_task,
                    answer_task
                ],
                process=Process.sequential,  # MUST be sequential - no parallel execution
                verbose=settings.CREWAI_VERBOSE,
                full_output=True
            )
            
            # Execute crew
            logger.info("Executing CrewAI sequential pipeline...")
            result = crew.kickoff()
            
            # Parse result
            final_output = self._parse_crew_output(result)
            
            # Calculate total duration
            total_duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log performance for each agent
            performance_logger.log_agent_execution(
                agent_name="RetrieverAgent",
                task_name="retrieval",
                duration_ms=retrieval_duration,
                success=True,
                token_count=0  # Would need to track from LLM
            )
            
            performance_logger.log_agent_execution(
                agent_name="ContextAgent",
                task_name="context_reconstruction",
                duration_ms=context_duration,
                success=True,
                token_count=0
            )
            
            performance_logger.log_agent_execution(
                agent_name="AnalystAgent",
                task_name="analysis",
                duration_ms=analysis_duration,
                success=True,
                token_count=0
            )
            
            performance_logger.log_agent_execution(
                agent_name="ComplianceAgent",
                task_name="compliance_review",
                duration_ms=compliance_duration,
                success=True,
                token_count=0
            )
            
            performance_logger.log_agent_execution(
                agent_name="AnswerAgent",
                task_name="answer_generation",
                duration_ms=answer_duration,
                success=True,
                token_count=0
            )
            
            # Add metadata
            final_output["metadata"] = {
                "request_id": request_id,
                "org_id": org_id,
                "user_id": user_id,
                "processing_time_ms": total_duration,
                "retrieval_count": len(retrieved_chunks),
                "agent_timings": {
                    "retriever_ms": retrieval_duration,
                    "context_ms": context_duration,
                    "analyst_ms": analysis_duration,
                    "compliance_ms": compliance_duration,
                    "answer_ms": answer_duration
                }
            }
            
            logger.info(
                f"RAG pipeline completed successfully in {total_duration:.2f}ms "
                f"for request_id={request_id}"
            )
            
            return final_output
            
        except Exception as e:
            logger.error(f"RAG pipeline failed for request_id={request_id}: {e}", exc_info=True)
            
            # Return error response
            return {
                "answer": (
                    "I encountered an error while processing your query. "
                    "Please try again or contact support if the issue persists."
                ),
                "sources": [],
                "answer_complete": False,
                "error": str(e),
                "metadata": {
                    "request_id": request_id,
                    "org_id": org_id,
                    "user_id": user_id,
                    "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "error": True
                }
            }
    
    def _parse_crew_output(self, result: Any) -> Dict[str, Any]:
        """
        Parse CrewAI output into standard format.
        
        Args:
            result: Raw CrewAI result
            
        Returns:
            Standardized response dictionary
        """
        try:
            # Try to parse as JSON
            if isinstance(result, str):
                parsed = json.loads(result)
            elif hasattr(result, 'raw'):
                parsed = json.loads(result.raw)
            elif hasattr(result, 'output'):
                parsed = json.loads(result.output)
            else:
                parsed = result
            
            # Extract answer and sources
            answer = parsed.get("answer", str(result))
            sources = parsed.get("sources", [])
            answer_complete = parsed.get("answer_complete", True)
            confidence = parsed.get("confidence", "medium")
            limitations = parsed.get("limitations", [])
            
            return {
                "answer": answer,
                "sources": sources,
                "answer_complete": answer_complete,
                "confidence": confidence,
                "limitations": limitations
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse crew output as JSON: {e}")
            
            # Fallback: return raw output
            return {
                "answer": str(result),
                "sources": [],
                "answer_complete": True,
                "confidence": "medium",
                "limitations": []
            }


# Singleton instance
_rag_crew: Optional[RAGCrew] = None


def get_rag_crew() -> RAGCrew:
    """Get or create RAGCrew singleton"""
    global _rag_crew
    
    if _rag_crew is None:
        _rag_crew = RAGCrew()
    
    return _rag_crew


# Export
__all__ = ["RAGCrew", "get_rag_crew"]
