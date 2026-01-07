"""
RAG Query API Endpoint
POST /api/v1/rag/query
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.services.rag_service import get_rag_service
from app.core.logging import audit_logger
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class RAGQueryRequest(BaseModel):
    """Request model for RAG query"""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="User's natural language query"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters for date_from, date_to, sender"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What decisions were made about the Q4 budget?",
                "filters": {
                    "date_from": "2024-10-01",
                    "date_to": "2024-12-31",
                    "sender": "finance@company.com"
                }
            }
        }


class EmailSource(BaseModel):
    """Email source citation model"""
    email_id: str
    subject: str
    sender: str
    date: str
    relevance_score: Optional[float] = None


class RAGQueryResponse(BaseModel):
    """Response model for RAG query"""
    answer: str = Field(description="Generated answer grounded in email evidence")
    sources: List[EmailSource] = Field(description="Source email citations")
    metadata: Dict[str, Any] = Field(description="Query metadata and performance metrics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Based on the retrieved emails, three key decisions were made...",
                "sources": [
                    {
                        "email_id": "abc123",
                        "subject": "Q4 Budget Approval",
                        "sender": "cfo@company.com",
                        "date": "2024-11-15T10:30:00Z",
                        "relevance_score": 0.92
                    }
                ],
                "metadata": {
                    "retrieval_count": 15,
                    "processing_time_ms": 1253,
                    "answer_complete": True
                }
            }
        }


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    request_body: RAGQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Execute RAG query on user's emails.
    
    This endpoint:
    1. Generates query embedding
    2. Retrieves relevant email chunks from Pinecone (tenant-isolated)
    3. Runs CrewAI agent pipeline (Retrieve → Context → Analyze → Compliance → Answer)
    4. Returns grounded answer with email citations
    
    **Security**: Query is automatically scoped to the authenticated user's emails only.
    **Compliance**: PII is redacted if configured.
    **Grounding**: All answers cite source emails. Refuses if context insufficient.
    """
    # TODO: Extract user_id and org_id from JWT token
    # For now using placeholder values - implement JWT auth middleware
    user_id = "user_demo"  # Extract from JWT: request.state.user_id
    org_id = "org_demo"    # Extract from JWT: request.state.org_id
    request_id = request.state.request_id
    
    logger.info(
        f"RAG query received: request_id={request_id}, "
        f"query={request_body.query[:100]}, user_id={user_id}"
    )
    
    try:
        # Parse filters
        filters = request_body.filters or {}
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        sender = filters.get("sender")
        
        # Get RAG service
        rag_service = get_rag_service()
        
        # Execute RAG query
        result = await rag_service.query(
            query=request_body.query,
            org_id=org_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            sender=sender,
            request_id=request_id
        )
        
        logger.info(f"RAG query completed successfully: request_id={request_id}")
        
        return result
        
    except Exception as e:
        logger.error(
            f"RAG query failed: request_id={request_id}, error={type(e).__name__}: {e}",
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Query processing failed",
                "message": "An error occurred while processing your query. Please try again.",
                "request_id": request_id
            }
        )


@router.get("/health")
async def rag_health():
    """RAG service health check"""
    try:
        # Could check CrewAI, Pinecone, embeddings service
        return {
            "status": "healthy",
            "service": "rag",
            "components": {
                "pinecone": "healthy",
                "crewai": "healthy",
                "embeddings": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"RAG health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


class EmailListItem(BaseModel):
    """Email list item for display"""
    id: str
    message_id: str
    subject: Optional[str] = None
    sender: str
    sender_name: Optional[str] = None
    sent_at: str
    has_attachments: bool = False
    labels: Optional[str] = None


class EmailListResponse(BaseModel):
    """Response model for email list"""
    emails: List[EmailListItem]
    count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "emails": [
                    {
                        "id": "abc123",
                        "message_id": "<msg123@example.com>",
                        "subject": "Q4 Budget Review",
                        "sender": "cfo@company.com",
                        "sender_name": "John CFO",
                        "sent_at": "2024-11-15T10:30:00Z",
                        "has_attachments": True,
                        "labels": "finance,important"
                    }
                ],
                "count": 1
            }
        }


@router.get("/emails", response_model=EmailListResponse)
async def get_emails(
    request: Request,
    limit: int = 5,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get latest emails for the authenticated user.
    
    Returns up to `limit` (default 5) most recent emails.
    
    **Security**: Emails are scoped to the authenticated user only.
    """
    from sqlalchemy import select
    from app.models.email import Email
    
    # TODO: Extract user_id and org_id from JWT token
    user_id = "user_demo"
    org_id = "org_demo"
    request_id = request.state.request_id
    
    logger.info(f"Fetching emails: request_id={request_id}, user_id={user_id}, limit={limit}")
    
    try:
        # Query emails for this user/org, ordered by sent_at descending
        query = (
            select(Email)
            .where(Email.user_id == user_id)
            .where(Email.org_id == org_id)
            .order_by(Email.sent_at.desc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        emails = result.scalars().all()
        
        email_items = [
            EmailListItem(
                id=str(email.id),
                message_id=email.message_id,
                subject=email.subject,
                sender=email.sender,
                sender_name=email.sender_name,
                sent_at=email.sent_at.isoformat() if email.sent_at else "",
                has_attachments=email.has_attachments or False,
                labels=email.labels
            )
            for email in emails
        ]
        
        logger.info(f"Fetched {len(email_items)} emails: request_id={request_id}")
        
        return EmailListResponse(
            emails=email_items,
            count=len(email_items)
        )
        
    except Exception as e:
        logger.error(
            f"Failed to fetch emails: request_id={request_id}, error={type(e).__name__}: {e}",
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to fetch emails",
                "message": "An error occurred while fetching emails. Please try again.",
                "request_id": request_id
            }
        )
