"""
Pinecone Index Operations
Upsert and query operations with namespace-based tenant isolation
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
import uuid

from app.vectorstore.pinecone_client import get_pinecone_index
from app.core.config import get_settings
from app.core.logging import performance_logger

settings = get_settings()
logger = logging.getLogger(__name__)


class PineconeIndexOperations:
    """
    High-level operations for Pinecone vector database.
    Enforces tenant isolation via namespaces.
    """
    
    def __init__(self):
        self.index = get_pinecone_index()
    
    def upsert_vectors(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
        namespace: str
    ) -> bool:
        """
        Upsert vectors into Pinecone with metadata.
        
        Args:
            vectors: List of (vector_id, embedding, metadata) tuples
            namespace: Tenant namespace (org_{org_id}_user_{user_id})
            
        Returns:
            True if successful, False otherwise
            
        SECURITY: Namespace must always be provided for tenant isolation.
        """
        if not namespace:
            logger.error("Cannot upsert without namespace - tenant isolation required")
            return False
        
        if not vectors:
            logger.warning("No vectors to upsert")
            return True
        
        try:
            start_time = datetime.now()
            
            # Prepare vectors for upsert
            # Pinecone expects: list of tuples (id, values, metadata)
            formatted_vectors = [
                (vec_id, embedding, metadata)
                for vec_id, embedding, metadata in vectors
            ]
            
            # Batch upsert
            batch_size = 100
            for i in range(0, len(formatted_vectors), batch_size):
                batch = formatted_vectors[i:i + batch_size]
                self.index.upsert(
                    vectors=batch,
                    namespace=namespace
                )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(
                f"Upserted {len(vectors)} vectors to namespace={namespace} "
                f"in {duration_ms:.2f}ms"
            )
            
            # Log performance metrics
            performance_logger.log_vector_query(
                namespace=namespace,
                query_vector_dim=settings.PINECONE_DIMENSION,
                top_k=len(vectors),
                filter_count=0,
                duration_ms=duration_ms,
                result_count=len(vectors)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to upsert vectors: {type(e).__name__}: {e}")
            return False
    
    def query_vectors(
        self,
        query_vector: List[float],
        namespace: str,
        top_k: int = 20,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Query vectors from Pinecone with optional metadata filtering.
        
        Args:
            query_vector: Embedding vector to search for
            namespace: Tenant namespace (org_{org_id}_user_{user_id})
            top_k: Number of results to return
            filter_dict: Metadata filters (e.g., {"sender": "user@example.com"})
            include_metadata: Whether to include metadata in results
            
        Returns:
            List of matching results with scores and metadata
            
        SECURITY: Namespace isolation enforced - users can only query their namespace.
        """
        if not namespace:
            logger.error("Cannot query without namespace - tenant isolation required")
            return []
        
        try:
            start_time = datetime.now()
            
            # Query Pinecone
            results = self.index.query(
                vector=query_vector,
                namespace=namespace,
                top_k=top_k,
                filter=filter_dict,
                include_metadata=include_metadata
            )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Extract matches
            matches = []
            for match in results.matches:
                match_data = {
                    "id": match.id,
                    "score": match.score,
                }
                if include_metadata:
                    match_data["metadata"] = match.metadata
                
                # Only include matches above relevance threshold
                if match.score >= settings.MIN_RELEVANCE_SCORE:
                    matches.append(match_data)
            
            logger.info(
                f"Query returned {len(matches)} matches from namespace={namespace} "
                f"(top_k={top_k}, filters={bool(filter_dict)}) in {duration_ms:.2f}ms"
            )
            
            # Log performance
            performance_logger.log_vector_query(
                namespace=namespace,
                query_vector_dim=len(query_vector),
                top_k=top_k,
                filter_count=len(filter_dict) if filter_dict else 0,
                duration_ms=duration_ms,
                result_count=len(matches)
            )
            
            return matches
            
        except Exception as e:
            logger.error(f"Failed to query vectors: {type(e).__name__}: {e}")
            return []
    
    def fetch_vectors_by_ids(
        self,
        vector_ids: List[str],
        namespace: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch specific vectors by ID.
        
        Args:
            vector_ids: List of vector IDs to fetch
            namespace: Tenant namespace
            
        Returns:
            Dictionary mapping vector_id to vector data
        """
        if not namespace or not vector_ids:
            return {}
        
        try:
            results = self.index.fetch(
                ids=vector_ids,
                namespace=namespace
            )
            
            logger.debug(f"Fetched {len(results.vectors)} vectors from namespace={namespace}")
            
            return {
                vec_id: {
                    "values": vec_data.values,
                    "metadata": vec_data.metadata
                }
                for vec_id, vec_data in results.vectors.items()
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch vectors: {e}")
            return {}
    
    def delete_vectors(
        self,
        vector_ids: List[str],
        namespace: str
    ) -> bool:
        """
        Delete specific vectors by ID.
        
        Args:
            vector_ids: List of vector IDs to delete
            namespace: Tenant namespace
            
        Returns:
            True if successful, False otherwise
        """
        if not namespace or not vector_ids:
            return False
        
        try:
            self.index.delete(
                ids=vector_ids,
                namespace=namespace
            )
            
            logger.info(f"Deleted {len(vector_ids)} vectors from namespace={namespace}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return False
    
    def delete_by_filter(
        self,
        filter_dict: Dict[str, Any],
        namespace: str
    ) -> bool:
        """
        Delete vectors matching metadata filter.
        Useful for deleting all vectors for a specific email.
        
        Args:
            filter_dict: Metadata filter (e.g., {"email_id": "abc123"})
            namespace: Tenant namespace
            
        Returns:
            True if successful, False otherwise
        """
        if not namespace or not filter_dict:
            return False
        
        try:
            self.index.delete(
                filter=filter_dict,
                namespace=namespace
            )
            
            logger.info(f"Deleted vectors matching filter={filter_dict} from namespace={namespace}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete by filter: {e}")
            return False
    
    def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """
        Get statistics for a specific namespace.
        
        Args:
            namespace: Tenant namespace
            
        Returns:
            Dictionary with namespace statistics
        """
        try:
            stats = self.index.describe_index_stats()
            
            namespace_stats = stats.namespaces.get(namespace, None)
            
            if namespace_stats:
                return {
                    "vector_count": namespace_stats.vector_count,
                    "namespace": namespace
                }
            else:
                return {
                    "vector_count": 0,
                    "namespace": namespace
                }
                
        except Exception as e:
            logger.error(f"Failed to get namespace stats: {e}")
            return {"vector_count": 0, "namespace": namespace}


# Singleton instance
_pinecone_ops: Optional[PineconeIndexOperations] = None


def get_pinecone_operations() -> PineconeIndexOperations:
    """Get or create PineconeIndexOperations singleton"""
    global _pinecone_ops
    
    if _pinecone_ops is None:
        _pinecone_ops = PineconeIndexOperations()
    
    return _pinecone_ops


# Export
__all__ = ["PineconeIndexOperations", "get_pinecone_operations"]
