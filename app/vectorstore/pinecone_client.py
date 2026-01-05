"""
Pinecone Client Initialization
Safe, production-ready Pinecone setup with error handling
"""
from typing import Optional
import logging
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class PineconeClient:
    """
    Singleton Pinecone client for managing vector database connection.
    Handles initialization, index creation, and connection management.
    """
    
    _instance: Optional["PineconeClient"] = None
    _pinecone: Optional[Pinecone] = None
    _index = None
    
    def __new__(cls):
        """Ensure singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Pinecone client (only once)"""
        if self._pinecone is None:
            self._initialize_client()
    
    def _initialize_client(self) -> None:
        """
        Initialize Pinecone client with API key.
        SECURITY: Never log API keys.
        """
        try:
            logger.info("Initializing Pinecone client...")
            
            self._pinecone = Pinecone(
                api_key=settings.PINECONE_API_KEY,
                # Environment is now deprecated in Pinecone v3, handled via serverless spec
            )
            
            logger.info("Pinecone client initialized successfully")
            
            # Ensure index exists
            self._ensure_index_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone client: {type(e).__name__}")
            raise RuntimeError("Pinecone initialization failed. Check PINECONE_API_KEY configuration.")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _ensure_index_exists(self) -> None:
        """
        Ensure Pinecone index exists, create if not.
        Uses serverless spec for cost-effective deployment.
        """
        try:
            index_name = settings.PINECONE_INDEX_NAME
            
            # List existing indexes
            existing_indexes = self._pinecone.list_indexes()
            index_names = [idx.name for idx in existing_indexes]
            
            if index_name not in index_names:
                logger.info(f"Creating Pinecone index: {index_name}")
                
                # Create serverless index
                self._pinecone.create_index(
                    name=index_name,
                    dimension=settings.PINECONE_DIMENSION,
                    metric=settings.PINECONE_METRIC,
                    spec=ServerlessSpec(
                        cloud='aws',  # or 'gcp' based on your preference
                        region='us-east-1'  # adjust based on your region
                    )
                )
                
                logger.info(f"Index '{index_name}' created successfully")
            else:
                logger.info(f"Index '{index_name}' already exists")
            
            # Connect to index
            self._index = self._pinecone.Index(index_name)
            
            # Verify index stats
            stats = self._index.describe_index_stats()
            logger.info(f"Index stats: {stats.total_vector_count} vectors across {stats.namespaces} namespaces")
            
        except Exception as e:
            logger.error(f"Failed to ensure index exists: {type(e).__name__}: {e}")
            raise
    
    def get_index(self):
        """
        Get Pinecone index instance.
        
        Returns:
            Pinecone Index object for upsert/query operations
        """
        if self._index is None:
            self._ensure_index_exists()
        return self._index
    
    def get_client(self) -> Pinecone:
        """Get Pinecone client instance"""
        if self._pinecone is None:
            self._initialize_client()
        return self._pinecone
    
    def health_check(self) -> bool:
        """
        Check if Pinecone connection is healthy.
        
        Returns:
            True if connection is working, False otherwise
        """
        try:
            index = self.get_index()
            stats = index.describe_index_stats()
            logger.debug(f"Pinecone health check passed: {stats.total_vector_count} vectors")
            return True
        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return False
    
    def get_index_stats(self) -> dict:
        """
        Get detailed index statistics.
        
        Returns:
            Dictionary with index stats including vector count per namespace
        """
        try:
            index = self.get_index()
            stats = index.describe_index_stats()
            
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": {
                    name: {"vector_count": ns.vector_count}
                    for name, ns in (stats.namespaces or {}).items()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}
    
    def delete_namespace(self, namespace: str) -> bool:
        """
        Delete all vectors in a namespace (for user data deletion).
        
        Args:
            namespace: Namespace to delete (format: org_{org_id}_user_{user_id})
            
        Returns:
            True if successful, False otherwise
        """
        try:
            index = self.get_index()
            
            # Delete all vectors in namespace
            index.delete(delete_all=True, namespace=namespace)
            
            logger.info(f"Deleted namespace: {namespace}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete namespace {namespace}: {e}")
            return False


# Singleton instance
_pinecone_client: Optional[PineconeClient] = None


def get_pinecone_client() -> PineconeClient:
    """
    Get or create Pinecone client singleton.
    Use this function throughout the application.
    """
    global _pinecone_client
    
    if _pinecone_client is None:
        _pinecone_client = PineconeClient()
    
    return _pinecone_client


def get_pinecone_index():
    """
    Convenience function to get Pinecone index directly.
    """
    client = get_pinecone_client()
    return client.get_index()


# Export
__all__ = ["PineconeClient", "get_pinecone_client", "get_pinecone_index"]
