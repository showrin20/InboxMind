"""
Email API Routes
Email listing and sync endpoints

## Getting Started with Email Access

To access your emails, you need to:

1. **Register/Login**: Get an access token
   - POST /api/v1/auth/register (email, password)
   - POST /api/v1/auth/login (email, password)

2. **Connect Gmail**: Link your Google account
   - GET /api/v1/oauth/google (initiates OAuth flow)
   - This grants read-only access to your Gmail

3. **Sync Emails**: Fetch emails from Gmail
   - POST /api/v1/emails/sync (requires Gmail connected)

4. **Access Emails**: List and read your synced emails
   - GET /api/v1/emails (list emails)
   - GET /api/v1/emails/{id} (get email details)

All endpoints require Bearer token authentication.
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_async_db
from app.models.email import Email
from app.models.user import User
from app.core.security import get_current_user
from app.services.email_sync_service import get_email_sync_service
from app.ui import (
    get_connect_gmail_page,
    get_email_list_page,
    get_email_detail_page,
)

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
    gmail_connected: bool


class GmailConnectionGuide(BaseModel):
    """Gmail connection instructions"""
    connected: bool
    message: str
    steps: List[str]
    oauth_url: str


@router.get("/connect-guide", response_model=GmailConnectionGuide)
async def gmail_connection_guide(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get instructions for connecting Gmail (JSON response).
    
    Returns step-by-step guide for linking your Google account
    to enable email sync and RAG queries.
    """
    user = await get_current_user(request, db)
    
    gmail_connected = bool(user.encrypted_access_token)
    
    if gmail_connected:
        return GmailConnectionGuide(
            connected=True,
            message="Gmail is connected! You can now sync emails.",
            steps=[
                "Your Gmail account is already connected.",
                "Use POST /api/v1/emails/sync to fetch emails.",
                "Use GET /api/v1/emails to view synced emails.",
                "Use POST /api/v1/rag/query to search your emails with AI."
            ],
            oauth_url="/api/v1/oauth/google"
        )
    
    return GmailConnectionGuide(
        connected=False,
        message="Gmail not connected. Follow these steps to connect.",
        steps=[
            "1. Open the OAuth URL in your browser (or use the link below)",
            "2. Sign in with your Google account",
            "3. Grant read-only access to Gmail",
            "4. You'll be redirected back with an access token",
            "5. Use the token for authenticated API calls",
            "6. Call POST /api/v1/emails/sync to fetch your emails"
        ],
        oauth_url="/api/v1/oauth/google"
    )


@router.get("/connect-guide/ui", response_class=HTMLResponse)
async def gmail_connection_guide_ui(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Show Gmail connection guide page UI.
    
    Displays a page to connect Gmail or shows connected status.
    Requires authentication.
    """
    user = await get_current_user(request, db)
    is_connected = bool(user.encrypted_access_token)
    
    html_content = get_connect_gmail_page(
        oauth_start_url="/api/v1/oauth/google",
        is_test=False,
        is_connected=is_connected
    )
    return HTMLResponse(content=html_content)


@router.get("", response_model=EmailListResponse)
async def list_emails(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Number of emails to return"),
    offset: int = Query(default=0, ge=0, description="Number of emails to skip"),
    sender: Optional[str] = Query(default=None, description="Filter by sender email"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List emails for the authenticated user.
    
    Returns paginated list of emails ordered by sent date (newest first).
    
    **Prerequisites:**
    - Must be authenticated with Bearer token
    - Gmail must be connected via OAuth
    - Emails must be synced via POST /emails/sync
    
    **If you get empty results:**
    1. Check /emails/connect-guide to verify Gmail is connected
    2. Run POST /emails/sync to fetch emails from Gmail
    """
    user = await get_current_user(request, db)
    
    logger.info(f"Listing emails for user {user.id}, limit={limit}, offset={offset}")
    
    # Build query with optional filters
    base_query = select(Email).where(
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    
    if sender:
        base_query = base_query.where(Email.sender.ilike(f"%{sender}%"))
    
    # Get total count
    count_query = select(func.count(Email.id)).where(
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    if sender:
        count_query = count_query.where(Email.sender.ilike(f"%{sender}%"))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # If no emails, provide helpful message
    if total == 0:
        logger.info(f"No emails found for user {user.id}")
    
    # Get emails
    query = (
        base_query
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
    
    Shows whether Gmail is connected and how many emails are synced.
    """
    user = await get_current_user(request, db)
    
    # Get email count
    count_query = select(func.count(Email.id)).where(
        Email.user_id == str(user.id),
        Email.org_id == user.org_id
    )
    result = await db.execute(count_query)
    email_count = result.scalar() or 0
    
    gmail_connected = bool(user.encrypted_access_token)
    
    return SyncStatusResponse(
        last_sync=user.last_email_sync,
        email_count=email_count,
        sync_enabled=user.email_sync_enabled,
        gmail_connected=gmail_connected
    )


@router.post("/sync", response_model=SyncResponse)
async def sync_emails(
    request: Request,
    max_emails: int = Query(default=100, ge=1, le=500, description="Maximum emails to sync"),
    since_days: int = Query(default=30, ge=1, le=365, description="Sync emails from last N days"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Sync emails from Gmail for the authenticated user.
    
    Fetches new emails from Gmail and stores them in the database.
    Also creates embeddings for RAG queries.
    
    **Prerequisites:**
    1. Must be authenticated
    2. Gmail must be connected via /api/v1/oauth/google
    
    **Parameters:**
    - max_emails: Maximum number of emails to sync (1-500)
    - since_days: Sync emails from the last N days (for initial sync)
    
    **If you get an error about Gmail access:**
    Visit GET /api/v1/oauth/google to connect your Gmail account.
    """
    user = await get_current_user(request, db)
    
    if not user.email_sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Email sync disabled",
                "message": "Email sync is disabled for this account.",
                "how_to_fix": "Contact support to enable email sync."
            }
        )
    
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Gmail not connected",
                "message": "You need to connect your Gmail account first.",
                "how_to_fix": "Visit /api/v1/oauth/google to connect Gmail.",
                "oauth_url": "/api/v1/oauth/google"
            }
        )
    
    logger.info(f"Starting email sync for user {user.id}, max={max_emails}, days={since_days}")
    
    try:
        sync_service = get_email_sync_service()
        
        synced, skipped, errors = await sync_service.sync_emails_for_user(
            db=db,
            user=user,
            max_emails=max_emails,
            since_days=since_days
        )
        
        logger.info(f"Email sync complete for user {user.id}: synced={synced}, skipped={skipped}")
        
        return SyncResponse(
            synced=synced,
            skipped=skipped,
            errors=errors[:10],  # Limit error messages
            message=f"Synced {synced} new emails, skipped {skipped} existing"
        )
    
    except Exception as e:
        logger.error(f"Email sync failed for user {user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Sync failed",
                "message": str(e),
                "how_to_fix": "Try reconnecting Gmail at /api/v1/oauth/google"
            }
        )


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email(
    email_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get full email details by ID.
    
    Returns the complete email including body text/HTML.
    Only returns emails belonging to the authenticated user.
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
            detail={
                "error": "Email not found",
                "message": f"No email with ID '{email_id}' found for your account.",
                "how_to_fix": "Use GET /api/v1/emails to list available emails."
            }
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


# ============== HTML UI Endpoints ==============

@router.get("/ui/connect", response_class=HTMLResponse)
async def email_connect_gmail_ui(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Show Gmail connection page UI.
    
    Displays a page to connect Gmail or shows connected status.
    Requires authentication.
    """
    user = await get_current_user(request, db)
    is_connected = bool(user.encrypted_access_token)
    
    html_content = get_connect_gmail_page(
        oauth_start_url="/api/v1/oauth/google",
        is_test=False,
        is_connected=is_connected
    )
    return HTMLResponse(content=html_content)


@router.get("/ui/list", response_class=HTMLResponse)
async def email_list_ui(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Show email list page UI.
    
    Displays paginated list of emails in a user-friendly HTML page.
    Requires authentication.
    """
    user = await get_current_user(request, db)
    
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
    
    email_list = [
        {
            "id": str(email.id),
            "message_id": email.message_id,
            "subject": email.subject,
            "sender": email.sender,
            "sender_name": email.sender_name,
            "sent_at": email.sent_at.isoformat() if email.sent_at else "",
            "has_attachments": email.has_attachments or False,
            "labels": email.labels
        }
        for email in emails
    ]
    
    html_content = get_email_list_page(
        emails=email_list,
        total=total,
        offset=offset,
        limit=limit,
        base_url="/api/v1/emails/ui/list",
        is_test=False
    )
    return HTMLResponse(content=html_content)


@router.get("/ui/view/{email_id}", response_class=HTMLResponse)
async def email_detail_ui(
    email_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Show email detail page UI.
    
    Displays full email content in a user-friendly HTML page.
    Requires authentication.
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
    
    email_data = {
        "id": str(email.id),
        "message_id": email.message_id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender": email.sender,
        "sender_name": email.sender_name,
        "recipients_to": email.recipients_to,
        "recipients_cc": email.recipients_cc,
        "sent_at": email.sent_at.isoformat() if email.sent_at else "",
        "body_text": email.body_text,
        "body_html": email.body_html,
        "has_attachments": email.has_attachments or False,
        "attachment_count": email.attachment_count or 0,
        "labels": email.labels
    }
    
    html_content = get_email_detail_page(
        email=email_data,
        back_url="/api/v1/emails/ui/list",
        is_test=False
    )
    return HTMLResponse(content=html_content)
