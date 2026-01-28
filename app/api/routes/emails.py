"""
Email API Routes
Fetches emails directly from Gmail - no database storage
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, status, Request, Query
from pydantic import BaseModel

from app.api.routes.dependencies import get_current_user_from_request, get_db_from_request
from app.ingestion.email_fetcher import create_gmail_fetcher_for_user

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Models
class EmailItem(BaseModel):
    """Email item"""
    message_id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    sender: str
    sender_name: Optional[str] = None
    recipients_to: Optional[List[str]] = None
    recipients_cc: Optional[List[str]] = None
    sent_at: Optional[str] = None
    body_text: Optional[str] = None
    has_attachments: bool = False
    labels: Optional[List[str]] = None


class EmailListResponse(BaseModel):
    """Email list response"""
    emails: List[EmailItem]
    count: int


@router.get("", response_model=EmailListResponse)
async def get_emails(
    request: Request,
    max_results: int = Query(default=50, ge=1, le=200, description="Number of emails to fetch"),
    days: int = Query(default=30, ge=1, le=365, description="Fetch emails from last N days")
):
    """
    Get emails directly from Gmail.
    
    Fetches emails from your Gmail inbox without storing them.
    
    **Prerequisites:**
    - Must be authenticated with Bearer token
    - Gmail must be connected via /api/v1/oauth/
    """
    user = get_current_user_from_request(request)
    db = get_db_from_request(request)
    
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Gmail not connected",
                "message": "Connect your Gmail account first",
                "oauth_url": "/api/v1/oauth/ui"
            }
        )
    
    logger.info(f"Fetching emails for user {user.id}, max_results={max_results}, days={days}")
    
    try:
        # Create Gmail fetcher with user's token
        fetcher = await create_gmail_fetcher_for_user(db, user)
        
        # Calculate since date
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Fetch emails from Gmail
        emails = []
        async for parsed_email in fetcher.fetch_emails_since(
            since_date=since_date,
            max_results=max_results,
            label_ids=["INBOX"]
        ):
            emails.append(EmailItem(
                message_id=parsed_email.message_id,
                thread_id=parsed_email.thread_id,
                subject=parsed_email.subject,
                sender=parsed_email.sender,
                sender_name=parsed_email.sender_name,
                recipients_to=parsed_email.recipients_to,
                recipients_cc=parsed_email.recipients_cc,
                sent_at=parsed_email.sent_at.isoformat() if parsed_email.sent_at else None,
                body_text=parsed_email.body_text[:500] if parsed_email.body_text else None,
                has_attachments=parsed_email.has_attachments,
                labels=parsed_email.labels
            ))
        
        logger.info(f"Fetched {len(emails)} emails for user {user.id}")
        
        return EmailListResponse(
            emails=emails,
            count=len(emails)
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch emails: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to fetch emails",
                "message": str(e),
                "oauth_url": "/api/v1/oauth/ui"
            }
        )


@router.get("/{message_id}")
async def get_email_detail(
    message_id: str,
    request: Request
):
    """
    Get full email details by message ID.
    
    Returns the complete email including full body text.
    """
    user = get_current_user_from_request(request)
    db = get_db_from_request(request)
    
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail not connected"
        )
    
    try:
        fetcher = await create_gmail_fetcher_for_user(db, user)
        
        # Fetch single email by ID
        parsed_email = await fetcher.fetch_email_by_id(message_id)
        
        if not parsed_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not found"
            )
        
        return {
            "message_id": parsed_email.message_id,
            "thread_id": parsed_email.thread_id,
            "subject": parsed_email.subject,
            "sender": parsed_email.sender,
            "sender_name": parsed_email.sender_name,
            "recipients_to": parsed_email.recipients_to,
            "recipients_cc": parsed_email.recipients_cc,
            "sent_at": parsed_email.sent_at.isoformat() if parsed_email.sent_at else None,
            "body_text": parsed_email.body_text,
            "body_html": parsed_email.body_html,
            "has_attachments": parsed_email.has_attachments,
            "attachment_count": parsed_email.attachment_count,
            "labels": parsed_email.labels
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch email: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
