"""
RAG Service - Orchestrates Complete Query-to-Answer Flow
Integrates: Vector search → CrewAI pipeline → Response formatting
"""
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import uuid

from app.embeddings.embedder import get_embedding_service
from app.vectorstore.pinecone_index import get_pinecone_operations
from app.vectorstore.filters import create_rag_query_filter
from app.crew.crew_runner import get_rag_crew
from app.core.config import get_settings
from app.core.logging import audit_logger

settings = get_settings()
logger = logging.getLogger(__name__)


class RAGService:
    """
    High-level RAG service that coordinates:
    1. Query embedding generation
    2. Vector database retrieval with filters
    3. CrewAI agent pipeline execution
    4. Response formatting
    """
    
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.pinecone_ops = get_pinecone_operations()
        self.rag_crew = get_rag_crew()
    
    async def query(
        self,
        query: str,
        org_id: str,
        user_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sender: Optional[str] = None,
        top_k: int = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute RAG query end-to-end.
        
        Args:
            query: User's natural language query
            org_id: Organization ID (tenant isolation)
            user_id: User ID (tenant isolation)
            date_from: Optional date filter (YYYY-MM-DD)
            date_to: Optional date filter (YYYY-MM-DD)
            sender: Optional sender email filter
            top_k: Max results to retrieve (default from settings)
            request_id: Optional request tracing ID
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        if top_k is None:
            top_k = settings.MAX_RETRIEVAL_RESULTS
        
        start_time = datetime.now()
        
        logger.info(
            f"RAG query started: request_id={request_id}, "
            f"query={query[:100]}, org_id={org_id}, user_id={user_id}"
        )
        
        try:
            # Step 1: Generate query embedding
            logger.debug(f"Generating query embedding for request_id={request_id}")
            query_embedding = await self.embedding_service.generate_query_embedding(query)
            
            # Step 2: Build namespace for tenant isolation
            namespace = settings.get_namespace(org_id, user_id)
            logger.debug(f"Using namespace: {namespace}")
            
            # Step 3: Build metadata filters
            filter_dict = create_rag_query_filter(
                org_id=org_id,
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
                sender=sender
            )
            
            # Step 4: Query Pinecone
            logger.debug(f"Querying Pinecone with top_k={top_k}")
            retrieved_chunks = self.pinecone_ops.query_vectors(
                query_vector=query_embedding,
                namespace=namespace,
                top_k=top_k,
                filter_dict=filter_dict,
                include_metadata=True
            )
            
            if not retrieved_chunks:
                logger.warning(f"No chunks retrieved for request_id={request_id}")
                return self._no_results_response(query, request_id, org_id, user_id)
            
            logger.info(f"Retrieved {len(retrieved_chunks)} chunks for request_id={request_id}")
            
            # Step 5: Execute CrewAI pipeline
            logger.debug("Executing CrewAI pipeline")
            crew_result = await self.rag_crew.run_rag_pipeline(
                user_query=query,
                retrieved_chunks=retrieved_chunks,
                org_id=org_id,
                user_id=user_id,
                request_id=request_id
            )
            
            # Step 6: Format response
            response = self._format_response(
                crew_result=crew_result,
                query=query,
                filters={
                    "date_from": date_from,
                    "date_to": date_to,
                    "sender": sender
                },
                start_time=start_time,
                request_id=request_id
            )
            
            # Step 7: Audit log
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            audit_logger.log_rag_query(
                user_id=user_id,
                org_id=org_id,
                query=query,
                filters={"date_from": date_from, "date_to": date_to, "sender": sender},
                result_count=len(retrieved_chunks),
                processing_time_ms=processing_time,
                request_id=request_id
            )
            
            logger.info(
                f"RAG query completed: request_id={request_id}, "
                f"processing_time={processing_time:.2f}ms"
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"RAG query failed: request_id={request_id}, error={type(e).__name__}: {e}",
                exc_info=True
            )
            
            return {
                "answer": (
                    "I encountered an error while processing your query. "
                    "Please try again or contact support if the issue persists."
                ),
                "sources": [],
                "metadata": {
                    "request_id": request_id,
                    "error": True,
                    "error_message": str(e),
                    "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
    
    def _no_results_response(
        self,
        query: str,
        request_id: str,
        org_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Generate response when no emails match the query"""
        return {
            "answer": (
                "I couldn't find any emails matching your query and filters. "
                "This could mean:\n\n"
                "1. No emails exist with the specified criteria\n"
                "2. The emails haven't been synced yet\n"
                "3. The filters are too restrictive\n\n"
                "Try:\n"
                "- Broadening your date range\n"
                "- Removing sender filters\n"
                "- Checking if email sync is complete"
            ),
            "sources": [],
            "metadata": {
                "request_id": request_id,
                "retrieval_count": 0,
                "processing_time_ms": 0,
                "no_results": True
            }
        }
    
    def _format_response(
        self,
        crew_result: Dict[str, Any],
        query: str,
        filters: Dict[str, Optional[str]],
        start_time: datetime,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Format CrewAI result into API response format.
        
        Returns standard API response structure.
        """
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Extract core fields
        answer = crew_result.get("answer", "")
        sources = crew_result.get("sources", [])
        metadata = crew_result.get("metadata", {})
        
        # Build response
        response = {
            "answer": answer,
            "sources": sources,
            "metadata": {
                "request_id": request_id,
                "query": query,
                "filters": filters,
                "retrieval_count": metadata.get("retrieval_count", 0),
                "processing_time_ms": processing_time,
                "answer_complete": crew_result.get("answer_complete", True),
                "confidence": crew_result.get("confidence", "medium"),
                "agent_timings": metadata.get("agent_timings", {})
            }
        }
        
        # Add limitations if present
        if crew_result.get("limitations"):
            response["limitations"] = crew_result["limitations"]
        
        return response


# Singleton
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create RAGService singleton"""
    global _rag_service
    
    if _rag_service is None:
        _rag_service = RAGService()
    
    return _rag_service


# Export
__all__ = ["RAGService", "get_rag_service"]
