"""
Email API Routes
Email listing and sync endpoints
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_async_db
from app.models.email import Email
from app.models.user import User
from app.core.security import get_current_user
from app.services.email_sync_service import get_email_sync_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Models
class EmailListItem(BaseModel):
    """Email list item"""
    id: str
    message_id: str
    subject: Optional[str] = None
    sender: str
    sender_name: Optional[str] = None
    sent_at: str
    has_attachments: bool = False
    labels: Optional[str] = None


class EmailListResponse(BaseModel):
    """Email list response"""
    emails: List[EmailListItem]
    count: int
    total: int


class EmailDetailResponse(BaseModel):
    """Full email detail"""
    id: str
    message_id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    sender: str
    sender_name: Optional[str] = None
    recipients_to: Optional[str] = None
    recipients_cc: Optional[str] = None
    sent_at: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    has_attachments: bool = False
    attachment_count: int = 0
    labels: Optional[str] = None


class SyncResponse(BaseModel):
    """Email sync response"""
    synced: int
    skipped: int
    errors: List[str] = []
    message: str


class SyncStatusResponse(BaseModel):
    """Sync status response"""
    last_sync: Optional[datetime] = None
    email_count: int
    sync_enabled: bool


@router.get("", response_model=EmailListResponse)
async def list_emails(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List emails for the authenticated user.
    
    Returns paginated list of emails ordered by sent date (newest first).
    """
    user = await get_current_user(request, db)
    
    logger.info(f"Listing emails for user {user.id}, limit={limit}, offset={offset}")
    
    # Get total count
    count_query = select(func.count(Email.id)).where(
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get emails
    query = (
        select(Email)
        .where(Email.user_id == str(user.id), Email.org_id == user.org_id)
        .order_by(Email.sent_at.desc())
        .offset(offset)
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
    
    return EmailListResponse(
        emails=email_items,
        count=len(email_items),
        total=total
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get email sync status for the authenticated user.
    """
    user = await get_current_user(request, db)
    
    # Get email count
    count_query = select(func.count(Email.id)).where(
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    result = await db.execute(count_query)
    email_count = result.scalar() or 0
    
    return SyncStatusResponse(
        last_sync=user.last_email_sync,
        email_count=email_count,
        sync_enabled=user.email_sync_enabled
    )


@router.post("/sync", response_model=SyncResponse)
async def sync_emails(
    request: Request,
    max_emails: int = Query(default=100, ge=1, le=500),
    since_days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Sync emails from Gmail for the authenticated user.
    
    Fetches new emails from Gmail and stores them in the database.
    
    Args:
        max_emails: Maximum number of emails to sync (1-500)
        since_days: Sync emails from the last N days (for first sync)
    """
    user = await get_current_user(request, db)
    
    if not user.email_sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sync is disabled for this account"
        )
    
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Gmail access. Please connect your Google account first at /api/v1/oauth/google"
        )
    
    logger.info(f"Starting email sync for user {user.id}")
    
    sync_service = get_email_sync_service()
    
    synced, skipped, errors = await sync_service.sync_emails_for_user(
        db=db,
        user=user,
        max_emails=max_emails,
        since_days=since_days
    )
    
    return SyncResponse(
        synced=synced,
        skipped=skipped,
        errors=errors[:10],  # Limit error messages
        message=f"Synced {synced} new emails, skipped {skipped} existing"
    )


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email(
    email_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get full email details by ID.
    """
    user = await get_current_user(request, db)
    
    # Get email (with tenant isolation)
    query = select(Email).where(
        Email.id == email_id,
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    
    result = await db.execute(query)
    email = result.scalar_one_or_none()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )
    
    return EmailDetailResponse(
        id=str(email.id),
        message_id=email.message_id,
        thread_id=email.thread_id,
        subject=email.subject,
        sender=email.sender,
        sender_name=email.sender_name,
        recipients_to=email.recipients_to,
        recipients_cc=email.recipients_cc,
        sent_at=email.sent_at.isoformat() if email.sent_at else "",
        body_text=email.body_text,
        body_html=email.body_html,
        has_attachments=email.has_attachments or False,
        attachment_count=email.attachment_count or 0,
        labels=email.labels
    )
