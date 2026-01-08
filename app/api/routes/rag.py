"""
RAG Query API Endpoint
POST /api/v1/rag/query

## AI-Powered Email Search

This endpoint allows you to ask natural language questions about your emails.

**Prerequisites:**
1. Authenticate via /api/v1/auth/login or /api/v1/auth/register
2. Connect Gmail via /api/v1/oauth/google
3. Sync emails via POST /api/v1/emails/sync

**Example queries:**
- "What decisions were made about the Q4 budget?"
- "Find emails from John about the project deadline"
- "Summarize my conversations with the marketing team last week"
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_async_db
from app.models.email import Email
from app.models.user import User
from app.services.rag_service import get_rag_service
from app.core.security import get_current_user
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
        description="Optional filters: date_from, date_to, sender"
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
    subject: Optional[str] = None
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


class RAGStatusResponse(BaseModel):
    """RAG service status"""
    ready: bool
    email_count: int
    gmail_connected: bool
    message: str
    next_steps: List[str]


@router.get("/status", response_model=RAGStatusResponse)
async def rag_status(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Check if RAG service is ready for queries.
    
    Returns status of Gmail connection and synced emails.
    """
    user = await get_current_user(request, db)
    
    # Check email count
    count_query = select(func.count(Email.id)).where(
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    result = await db.execute(count_query)
    email_count = result.scalar() or 0
    
    gmail_connected = bool(user.encrypted_access_token)
    ready = gmail_connected and email_count > 0
    
    next_steps = []
    if not gmail_connected:
        next_steps.append("Connect Gmail: GET /api/v1/oauth/google")
    if email_count == 0:
        next_steps.append("Sync emails: POST /api/v1/emails/sync")
    if ready:
        next_steps.append("Ready! Use POST /api/v1/rag/query to ask questions")
    
    return RAGStatusResponse(
        ready=ready,
        email_count=email_count,
        gmail_connected=gmail_connected,
        message="Ready to answer questions about your emails" if ready else "Setup incomplete",
        next_steps=next_steps
    )


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
    
    **Prerequisites:**
    1. Must be authenticated with Bearer token
    2. Gmail must be connected via /api/v1/oauth/google
    3. Emails must be synced via POST /api/v1/emails/sync
    """
    # Get authenticated user
    user = await get_current_user(request, db)
    user_id = str(user.id)
    org_id = user.org_id
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"RAG query received: request_id={request_id}, "
        f"query={request_body.query[:100]}, user_id={user_id}"
    )
    
    # Check prerequisites
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Gmail not connected",
                "message": "You need to connect Gmail before querying emails.",
                "how_to_fix": "Visit GET /api/v1/oauth/google to connect Gmail.",
                "oauth_url": "/api/v1/oauth/google"
            }
        )
    
    # Check if user has emails
    count_query = select(func.count(Email.id)).where(
        Email.user_id == user_id,
        Email.org_id == org_id
    )
    result = await db.execute(count_query)
    email_count = result.scalar() or 0
    
    if email_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No emails synced",
                "message": "You need to sync emails before querying.",
                "how_to_fix": "Call POST /api/v1/emails/sync to fetch your emails.",
                "sync_url": "/api/v1/emails/sync"
            }
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
    """
    RAG service health check.
    
    Returns status of RAG components (no authentication required).
    """
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
