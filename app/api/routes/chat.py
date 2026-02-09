"""
Chat API Endpoint
POST /api/v1/chat/message - Send chat messages about your emails
POST /api/v1/chat/vectorize - Vectorize emails for semantic search
GET /api/v1/chat/status - Check vectorization status

## AI-Powered Email Chat

This endpoint provides a conversational interface to query your emails.

**Prerequisites:**
1. Authenticate via /api/v1/auth/login or /api/v1/auth/register
2. Connect Gmail via /api/v1/oauth/google
3. Sync emails via POST /api/v1/emails/sync
4. Vectorize emails via POST /api/v1/chat/vectorize

**Example queries:**
- "Summarize my last 3 emails"
- "What did John say about the project?"
- "Find emails about budget from last week"
- "Show my unread emails"
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.chat_service import get_chat_service
from app.api.routes.dependencies import get_current_user_from_request, get_db_from_request
from app.core.logging import audit_logger
import logging

logger = logging.getLogger(__name__)

router = APIRouter()




class ChatMessageRequest(BaseModel):
    """Request model for chat message"""
    message: str = Field(
        ...,
        min_length=2,
        max_length=2000,
        description="Your question or command about emails"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters: date_from, date_to, sender"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Summarize my last 3 emails",
                "filters": None
            }
        }


class ChatMessageResponse(BaseModel):
    """Response model for chat message"""
    answer: str = Field(description="AI-generated response based on your emails")
    sources: List[Dict[str, Any]] = Field(description="Source emails referenced")
    metadata: Dict[str, Any] = Field(description="Query metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Here's a summary of your last 3 emails...",
                "sources": [
                    {
                        "email_id": "abc123",
                        "subject": "Project Update",
                        "sender": "john@example.com",
                        "date": "2024-01-15T10:30:00Z"
                    }
                ],
                "metadata": {
                    "request_id": "uuid-here",
                    "processing_time_ms": 1234
                }
            }
        }


class VectorizeRequest(BaseModel):
    """Request model for vectorization"""
    force_reindex: bool = Field(
        default=False,
        description="If True, re-vectorize all emails including already embedded ones"
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Number of emails to process per batch"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "force_reindex": False,
                "batch_size": 50
            }
        }


class VectorizeResponse(BaseModel):
    """Response model for vectorization"""
    status: str
    message: str
    vectorized_count: int
    total_chunks: int
    processing_time_ms: float
    errors: Optional[List[str]] = None


class VectorizationStatusResponse(BaseModel):
    """Response model for vectorization status"""
    total_emails: int
    embedded_emails: int
    pending_emails: int
    vector_count: int
    is_ready: bool
    completion_percentage: float
    message: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(request_body: ChatMessageRequest, request: Request):
    """
    Send a chat message to query your emails.
    
    **Features:**
    - Natural language queries about your emails
    - Special commands like "summarize last 3 emails"
    - Semantic search using vector embeddings
    - Filter by date range or sender
    
    **Special Commands:**
    - `summarize last N emails` - Get a summary of your most recent emails
    - `show my unread emails` - List unread emails
    - `what are my recent 5 mails` - Show recent emails
    
    **Example Queries:**
    - "What decisions were made about the Q4 budget?"
    - "Summarize my last 5 emails"
    - "Find emails from john@example.com about the project"
    - "What did marketing say about the campaign?"
    
    **Prerequisites:**
    1. Emails must be synced via POST /api/v1/emails/sync
    2. Emails must be vectorized via POST /api/v1/chat/vectorize
    """
    user = get_current_user_from_request(request)
    db = get_db_from_request(request)
    
    user_id = str(user.id)
    org_id = user.org_id
    request_id = getattr(request.state, "request_id", None)
    
    logger.info(f"Chat message: request_id={request_id}, message={request_body.message[:100]}")
    
    # Check prerequisites
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Gmail not connected",
                "message": "Please connect Gmail before using chat.",
                "how_to_fix": "Visit GET /api/v1/oauth/google to connect Gmail."
            }
        )
    
    try:
        chat_service = get_chat_service()
        
        result = await chat_service.chat(
            db=db,
            query=request_body.message,
            org_id=org_id,
            user_id=user_id,
            filters=request_body.filters,
            request_id=request_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Chat message failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Chat processing failed",
                "message": "An error occurred while processing your message.",
                "request_id": request_id
            }
        )


@router.post("/vectorize", response_model=VectorizeResponse)
async def vectorize_emails(
    request: Request,
    request_body: Optional[VectorizeRequest] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Vectorize all emails for semantic search.
    
    This endpoint:
    1. Reads all synced emails from the database
    2. Chunks email body_text into smaller pieces
    3. Generates embeddings using Google Gemini
    4. Stores vectors in Pinecone for semantic search
    
    **Important:**
    - First-time vectorization may take a while depending on email count
    - Run this after syncing emails
    - Use `force_reindex=True` to re-vectorize all emails
    
    **Prerequisites:**
    - Emails must be synced via POST /api/v1/emails/sync
    """
    user = get_current_user_from_request(request)
    db = get_db_from_request(request)
    
    user_id = str(user.id)
    org_id = user.org_id
    
    if request_body is None:
        request_body = VectorizeRequest()
    
    logger.info(f"Starting vectorization for user {user_id}, force_reindex={request_body.force_reindex}")
    
    try:
        chat_service = get_chat_service()
        
        result = await chat_service.vectorize_emails(
            db=db,
            org_id=org_id,
            user_id=user_id,
            batch_size=request_body.batch_size,
            force_reindex=request_body.force_reindex
        )
        
        return VectorizeResponse(**result)
        
    except Exception as e:
        logger.error(f"Vectorization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Vectorization failed",
                "message": str(e)
            }
        )


@router.get("/status", response_model=VectorizationStatusResponse)
async def vectorization_status(request: Request):
    """
    Check the vectorization status of your emails.
    
    Returns:
    - Total email count
    - Number of vectorized emails
    - Number of pending emails
    - Vector count in Pinecone
    - Whether chat is ready to use
    """
    user = get_current_user_from_request(request)
    db = get_db_from_request(request)
    
    user_id = str(user.id)
    org_id = user.org_id
    
    try:
        chat_service = get_chat_service()
        
        status_data = await chat_service.get_vectorization_status(
            db=db,
            org_id=org_id,
            user_id=user_id
        )
        
        # Build message
        if status_data["total_emails"] == 0:
            message = "No emails synced. Please sync emails first: POST /api/v1/emails/sync"
        elif status_data["embedded_emails"] == 0:
            message = "Emails synced but not vectorized. Please vectorize: POST /api/v1/chat/vectorize"
        elif status_data["pending_emails"] > 0:
            message = f"Partially vectorized. {status_data['pending_emails']} emails pending. Run POST /api/v1/chat/vectorize"
        else:
            message = "All emails vectorized! Chat is ready to use."
        
        return VectorizationStatusResponse(
            **status_data,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Status check failed", "message": str(e)}
        )


@router.get("/health")
async def chat_health():
    """
    Chat service health check (no authentication required).
    """
    try:
        return {
            "status": "healthy",
            "service": "chat",
            "components": {
                "pinecone": "healthy",
                "gemini": "healthy",
                "embeddings": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"Chat health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
