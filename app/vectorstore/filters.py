"""
Metadata Filters for Vector Search
Constructs Pinecone filter dictionaries for tenant isolation and query refinement
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class VectorStoreFilters:
    """
    Build metadata filter dictionaries for Pinecone queries.
    Ensures tenant isolation and supports date/sender filtering.
    """
    
    @staticmethod
    def build_base_tenant_filter(org_id: str, user_id: str) -> Dict[str, Any]:
        """
        Build base filter enforcing tenant isolation.
        MUST be included in every query.
        
        Args:
            org_id: Organization ID
            user_id: User ID
            
        Returns:
            Pinecone filter dict with tenant constraints
        """
        return {
            "org_id": {"$eq": org_id},
            "user_id": {"$eq": user_id}
        }
    
    @staticmethod
    def build_date_range_filter(
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Build date range filter for sent_at metadata.
        
        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            
        Returns:
            Pinecone filter dict for date range or None
        """
        if not date_from and not date_to:
            return None
        
        filter_dict = {}
        
        if date_from:
            # Convert to ISO string for Pinecone
            filter_dict["$gte"] = date_from.isoformat()
        
        if date_to:
            filter_dict["$lte"] = date_to.isoformat()
        
        return {"sent_at": filter_dict} if filter_dict else None
    
    @staticmethod
    def build_sender_filter(sender: str) -> Dict[str, Any]:
        """
        Build sender filter.
        
        Args:
            sender: Email address of sender
            
        Returns:
            Pinecone filter dict for sender
        """
        return {"sender": {"$eq": sender}}
    
    @staticmethod
    def build_thread_filter(thread_id: str) -> Dict[str, Any]:
        """
        Build thread filter to retrieve all emails in a conversation.
        
        Args:
            thread_id: Email thread ID
            
        Returns:
            Pinecone filter dict for thread
        """
        return {"thread_id": {"$eq": thread_id}}
    
    @staticmethod
    def build_email_filter(email_id: str) -> Dict[str, Any]:
        """
        Build filter for specific email.
        
        Args:
            email_id: Email ID
            
        Returns:
            Pinecone filter dict for email
        """
        return {"email_id": {"$eq": email_id}}
    
    @staticmethod
    def combine_filters(
        org_id: str,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sender: Optional[str] = None,
        thread_id: Optional[str] = None,
        email_id: Optional[str] = None,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Combine multiple filters with AND logic.
        Always includes tenant isolation.
        
        Args:
            org_id: Organization ID (required)
            user_id: User ID (required)
            date_from: Optional start date
            date_to: Optional end date
            sender: Optional sender email
            thread_id: Optional thread ID
            email_id: Optional specific email ID
            additional_filters: Optional custom filters
            
        Returns:
            Combined Pinecone filter dict
        """
        # Start with tenant isolation (REQUIRED)
        filters = []
        filters.append(VectorStoreFilters.build_base_tenant_filter(org_id, user_id))
        
        # Add date range filter
        date_filter = VectorStoreFilters.build_date_range_filter(date_from, date_to)
        if date_filter:
            filters.append(date_filter)
        
        # Add sender filter
        if sender:
            filters.append(VectorStoreFilters.build_sender_filter(sender))
        
        # Add thread filter
        if thread_id:
            filters.append(VectorStoreFilters.build_thread_filter(thread_id))
        
        # Add email filter
        if email_id:
            filters.append(VectorStoreFilters.build_email_filter(email_id))
        
        # Add custom filters
        if additional_filters:
            filters.append(additional_filters)
        
        # Combine with $and
        if len(filters) == 1:
            combined = filters[0]
        else:
            combined = {"$and": filters}
        
        logger.debug(f"Built combined filter: {combined}")
        return combined
    
    @staticmethod
    def validate_filter(filter_dict: Dict[str, Any]) -> bool:
        """
        Validate that filter includes tenant isolation.
        
        Args:
            filter_dict: Pinecone filter dictionary
            
        Returns:
            True if valid (includes tenant fields), False otherwise
        """
        # Check if org_id and user_id are present
        filter_str = str(filter_dict)
        
        has_org = "org_id" in filter_str
        has_user = "user_id" in filter_str
        
        if not (has_org and has_user):
            logger.error(f"Filter missing tenant isolation: {filter_dict}")
            return False
        
        return True


def create_rag_query_filter(
    org_id: str,
    user_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sender: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to create filter for RAG queries.
    Converts string dates to datetime objects.
    
    Args:
        org_id: Organization ID
        user_id: User ID
        date_from: Start date string (YYYY-MM-DD)
        date_to: End date string (YYYY-MM-DD)
        sender: Sender email address
        
    Returns:
        Pinecone filter dictionary
    """
    # Convert string dates to datetime
    dt_from = None
    dt_to = None
    
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            logger.warning(f"Invalid date_from format: {date_from}")
    
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
        except ValueError:
            logger.warning(f"Invalid date_to format: {date_to}")
    
    return VectorStoreFilters.combine_filters(
        org_id=org_id,
        user_id=user_id,
        date_from=dt_from,
        date_to=dt_to,
        sender=sender
    )


# Export
__all__ = ["VectorStoreFilters", "create_rag_query_filter"]
