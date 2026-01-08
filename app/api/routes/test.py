"""
Test API Routes (Unauthenticated)
For development and testing purposes only.
These routes bypass authentication and use demo user/org.

WARNING: Disable these routes in production by setting APP_ENV != 'development'
"""
import logging
import secrets
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from urllib.parse import urlencode

from app.db.session import get_async_db
from app.models.email import Email
from app.models.user import User
from app.services.rag_service import get_rag_service
from app.services.email_sync_service import get_email_sync_service
from app.services.token_service import get_token_service
from app.core.config import get_settings
from app.ui import (
    get_connect_gmail_page,
    get_email_list_page,
    get_email_detail_page,
    get_oauth_error_page,
    get_oauth_success_page,
    get_oauth_missing_params_page,
    get_oauth_invalid_state_page,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()

# Demo user for unauthenticated testing
DEMO_USER_ID = "test_user_001"
DEMO_ORG_ID = "test_org_001"

# In-memory state storage for test OAuth
_test_oauth_states: dict = {}


# ============== Request/Response Models ==============

class TestRAGQueryRequest(BaseModel):
    """Request model for test RAG query"""
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
    user_id: Optional[str] = Field(
        default=None,
        description="Override test user_id (for testing multi-tenancy)"
    )
    org_id: Optional[str] = Field(
        default=None,
        description="Override test org_id (for testing multi-tenancy)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What decisions were made about the Q4 budget?",
                "filters": {
                    "date_from": "2024-10-01",
                    "date_to": "2024-12-31"
                },
                "user_id": "test_user_001",
                "org_id": "test_org_001"
            }
        }


class TestEmailSource(BaseModel):
    """Email source citation model"""
    email_id: str
    subject: str
    sender: str
    date: str
    relevance_score: Optional[float] = None


class TestRAGQueryResponse(BaseModel):
    """Response model for test RAG query"""
    answer: str
    sources: List[TestEmailSource]
    metadata: Dict[str, Any]
    test_info: Dict[str, str] = Field(
        description="Test context info showing which user/org was used"
    )


class TestEmailListItem(BaseModel):
    """Email list item"""
    id: str
    message_id: str
    subject: Optional[str] = None
    sender: str
    sender_name: Optional[str] = None
    sent_at: str
    has_attachments: bool = False
    labels: Optional[str] = None


class TestEmailListResponse(BaseModel):
    """Email list response with test context"""
    emails: List[TestEmailListItem]
    count: int
    total: int
    test_info: Dict[str, str]


class TestEmailDetailResponse(BaseModel):
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
    test_info: Dict[str, str]


# ============== Test Endpoints ==============

class TestInfoResponse(BaseModel):
    """Response model for test info endpoint"""
    message: str
    warning: str
    demo_credentials: Dict[str, str]
    available_endpoints: Dict[str, str]
    quick_start: str
    instructions: List[str]
    next_steps: Dict[str, str]

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Test routes are enabled (development mode)",
                "warning": "These routes bypass authentication. Do NOT use in production.",
                "demo_credentials": {
                    "user_id": "test_user_001",
                    "org_id": "test_org_001"
                },
                "available_endpoints": {
                    "GET /api/v1/test/info": "This endpoint"
                },
                "quick_start": "Visit /api/v1/test/connect-gmail to authorize Gmail access",
                "instructions": ["Step 1: Open connect-gmail endpoint"],
                "next_steps": {"1_connect": "http://localhost:8000/api/v1/test/connect-gmail"}
            }
        }


@router.get("/info", response_model=TestInfoResponse)
async def test_info(request: Request):
    """
    Get test route information.
    
    Returns info about the test endpoints and demo credentials.
    """
    base_url = str(request.base_url).rstrip('/')
    
    return JSONResponse(content={
        "message": "Test routes are enabled (development mode)",
        "warning": "These routes bypass authentication. Do NOT use in production.",
        "demo_credentials": {
            "user_id": DEMO_USER_ID,
            "org_id": DEMO_ORG_ID
        },
        "available_endpoints": {
            "GET /api/v1/test/info": "This endpoint - shows all available test routes",
            "GET /api/v1/test/connect-gmail": "Start Gmail OAuth flow (opens consent screen)",
            "GET /api/v1/test/oauth/start": "Redirects to Google OAuth consent page",
            "GET /api/v1/test/oauth/callback": "OAuth callback handler (internal)",
            "GET /api/v1/test/emails": "List emails JSON (no auth required)",
            "GET /api/v1/test/emails/{email_id}": "Get email details JSON (no auth required)",
            "GET /api/v1/test/emails/count/summary": "Get email count summary",
            "POST /api/v1/test/rag/query": "Execute RAG query (no auth required)",
            "GET /api/v1/test/users": "List all users in system",
            "GET /api/v1/test/ui/emails": "📧 View emails in HTML UI (no auth required)",
            "GET /api/v1/test/ui/emails/{email_id}": "📧 View email detail in HTML UI (no auth required)"
        },
        "ui_pages": {
            "connect_gmail": f"{base_url}/api/v1/test/connect-gmail",
            "email_list": f"{base_url}/api/v1/test/ui/emails",
            "email_detail": f"{base_url}/api/v1/test/ui/emails/{{email_id}}"
        },
        "instructions": [
            "Step 1: Open your browser and go to /api/v1/test/connect-gmail",
            "Step 2: Click 'Connect Gmail Account' button on the page",
            "Step 3: You will be redirected to Google's consent screen",
            "Step 4: Review and approve the Gmail read permissions",
            "Step 5: After authorization, emails from the last 30 days will sync automatically",
            "Step 6: You'll see a success page with your user_id and org_id",
            "Step 7: View your emails at /api/v1/test/ui/emails"
        ],
        "next_steps": {
            "1_connect_gmail": f"{base_url}/api/v1/test/connect-gmail",
            "2_view_emails_ui": f"{base_url}/api/v1/test/ui/emails",
            "3_list_emails_json": f"{base_url}/api/v1/test/emails?limit=20",
            "4_check_email_count": f"{base_url}/api/v1/test/emails/count/summary",
            "5_rag_query": f"{base_url}/api/v1/test/rag/query"
        },
        "quick_start": f"Open {base_url}/api/v1/test/connect-gmail in your browser to authorize Gmail access and sync emails"
    })


# ============== OAuth Flow for Testing ==============

@router.get("/connect-gmail", response_class=HTMLResponse)
async def test_connect_gmail_page(request: Request):
    """
    Show a page explaining Gmail connection and start OAuth flow.
    
    This page explains what permissions are requested and provides
    a button to start the OAuth flow.
    """
    html_content = get_connect_gmail_page(
        oauth_start_url="/api/v1/test/oauth/start",
        is_test=True,
        is_connected=False
    )
    return HTMLResponse(content=html_content)


@router.get("/oauth/start")
async def test_oauth_start(request: Request):
    """
    Start the Google OAuth flow for testing.
    
    Redirects to Google's consent screen.
    """
    # Generate secure state token
    state = secrets.token_urlsafe(32)
    _test_oauth_states[state] = {
        "created_at": datetime.now(timezone.utc),
        "request_id": getattr(request.state, "request_id", None)
    }
    
    # Use test-specific callback URL
    redirect_uri = str(request.base_url).rstrip('/') + "/api/v1/test/oauth/callback"
    
    # Build OAuth URL
    oauth_params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join([
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]),
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }
    
    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(oauth_params)}"
    
    logger.info(f"[TEST] Starting OAuth flow, state={state[:8]}...")
    
    return RedirectResponse(url=oauth_url)


@router.get("/oauth/callback", response_class=HTMLResponse)
async def test_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle Google OAuth callback for testing.
    
    Creates/updates user, stores tokens, and syncs emails automatically.
    """
    import aiohttp
    
    # Handle OAuth errors
    if error:
        logger.warning(f"[TEST] OAuth error: {error}")
        return HTMLResponse(content=get_oauth_error_page(
            error=error,
            retry_url="/api/v1/test/connect-gmail",
            is_test=True
        ))
    
    if not code or not state:
        return HTMLResponse(content=get_oauth_missing_params_page(
            retry_url="/api/v1/test/connect-gmail",
            is_test=True
        ))
    
    # Verify state token
    if state not in _test_oauth_states:
        logger.warning(f"[TEST] Invalid OAuth state: {state[:8]}...")
        return HTMLResponse(content=get_oauth_invalid_state_page(
            retry_url="/api/v1/test/connect-gmail",
            is_test=True
        ))
    
    del _test_oauth_states[state]
    
    # Exchange code for tokens
    redirect_uri = str(request.base_url).rstrip('/') + "/api/v1/test/oauth/callback"
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Exchange code for tokens
            async with session.post(token_url, data=token_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[TEST] Token exchange failed: {error_text}")
                    return HTMLResponse(content=f"""
                    <html><body>
                        <h2>❌ Token Exchange Failed</h2>
                        <p>Error: {error_text}</p>
                        <p><a href="/api/v1/test/connect-gmail">Try again</a></p>
                    </body></html>
                    """)
                
                tokens = await response.json()
            
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)
            
            # Get user info
            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(userinfo_url, headers=headers) as response:
                if response.status != 200:
                    return HTMLResponse(content="""
                    <html><body>
                        <h2>❌ Failed to get user info</h2>
                        <p><a href="/api/v1/test/connect-gmail">Try again</a></p>
                    </body></html>
                    """)
                
                user_info = await response.json()
        
        google_id = user_info["id"]
        email = user_info["email"]
        full_name = user_info.get("name", "")
        
        # Find or create user
        result = await db.execute(
            select(User).where(
                User.oauth_provider == "google",
                User.oauth_provider_id == google_id
            )
        )
        user = result.scalar_one_or_none()
        
        token_service = get_token_service()
        
        if user:
            logger.info(f"[TEST] Existing user found: {email}")
            user.full_name = full_name
        else:
            # Check if email exists
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                user = existing_user
                user.oauth_provider = "google"
                user.oauth_provider_id = google_id
                logger.info(f"[TEST] Linked Google to existing user: {email}")
            else:
                # Create new user with test org
                user = User(
                    email=email,
                    org_id=DEMO_ORG_ID,  # Use test org
                    full_name=full_name,
                    oauth_provider="google",
                    oauth_provider_id=google_id,
                    is_active=True,
                    email_sync_enabled=True
                )
                db.add(user)
                await db.flush()
                logger.info(f"[TEST] Created new user: {email}")
        
        # Store encrypted tokens
        if refresh_token:
            await token_service.store_oauth_tokens(
                db=db,
                user=user,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in
            )
        else:
            from datetime import timedelta
            user.encrypted_access_token = token_service.encrypt_token(access_token)
            user.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        await db.commit()
        await db.refresh(user)
        
        # Capture user details before sync (to avoid greenlet errors later)
        user_id_str = str(user.id)
        user_org_id = user.org_id
        user_email = user.email
        
        # Now sync emails
        sync_service = get_email_sync_service()
        synced_count, skipped_count, sync_errors = await sync_service.sync_emails_for_user(
            db=db,
            user=user,
            max_emails=50,  # Sync last 50 emails
            since_days=30   # From last 30 days
        )
        
        # Return success page (using captured values to avoid greenlet errors)
        return HTMLResponse(content=get_oauth_success_page(
            user_email=user_email,
            user_id=user_id_str,
            org_id=user_org_id,
            synced_count=synced_count,
            emails_url=f"/api/v1/test/emails?user_id={user_id_str}&org_id={user_org_id}",
            is_test=True
        ))
        
    except Exception as e:
        logger.error(f"[TEST] OAuth callback failed: {e}", exc_info=True)
        return HTMLResponse(content=get_oauth_error_page(
            error=str(e),
            retry_url="/api/v1/test/connect-gmail",
            is_test=True
        ))


@router.get("/users")
async def test_list_users(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    List all users in the system (for testing).
    
    Shows user IDs and org IDs to use with other test endpoints.
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "org_id": u.org_id,
                "oauth_provider": u.oauth_provider,
                "is_active": u.is_active,
                "email_sync_enabled": u.email_sync_enabled,
                "last_email_sync": u.last_email_sync.isoformat() if u.last_email_sync else None,
                "has_oauth_token": bool(u.encrypted_access_token)
            }
            for u in users
        ],
        "count": len(users),
        "tip": "Use any user's id and org_id with the test email/rag endpoints"
    }


@router.post("/sync-emails")
async def test_sync_emails(
    request: Request,
    user_id: str = Query(..., description="User ID to sync emails for"),
    max_emails: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Manually trigger email sync for a user (NO AUTH REQUIRED).
    
    Use this to re-sync emails for a user who has already connected Gmail.
    """
    # Find user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "User not found",
                "message": f"No user with id '{user_id}'",
                "how_to_fix": "Check available users at GET /api/v1/test/users"
            }
        )
    
    if not user.encrypted_access_token:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No Gmail connected",
                "message": "This user hasn't connected their Gmail account",
                "how_to_fix": "Visit /api/v1/test/connect-gmail to authorize Gmail access"
            }
        )
    
    # Sync emails
    sync_service = get_email_sync_service()
    synced_count, skipped_count, errors = await sync_service.sync_emails_for_user(
        db=db,
        user=user,
        max_emails=max_emails,
        since_days=30
    )
    
    return {
        "success": True,
        "synced": synced_count,
        "skipped": skipped_count,
        "errors": errors[:10] if errors else [],
        "user": {
            "id": str(user.id),
            "email": user.email,
            "org_id": user.org_id
        }
    }


@router.get("/emails", response_model=TestEmailListResponse)
async def test_list_emails(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = Query(default=None, description="Override test user_id"),
    org_id: Optional[str] = Query(default=None, description="Override test org_id"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List emails for testing (NO AUTHENTICATION REQUIRED).
    
    Uses demo user/org by default, or custom user_id/org_id if provided.
    
    Returns paginated list of emails ordered by sent date (newest first).
    """
    test_user_id = user_id or DEMO_USER_ID
    test_org_id = org_id or DEMO_ORG_ID
    
    logger.info(
        f"[TEST] Listing emails: user_id={test_user_id}, org_id={test_org_id}, "
        f"limit={limit}, offset={offset}"
    )
    
    try:
        # Get total count
        count_query = select(func.count(Email.id)).where(
            Email.user_id == test_user_id,
            Email.org_id == test_org_id
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get emails
        query = (
            select(Email)
            .where(Email.user_id == test_user_id, Email.org_id == test_org_id)
            .order_by(Email.sent_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        result = await db.execute(query)
        emails = result.scalars().all()
        
        email_items = [
            TestEmailListItem(
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
        
        return TestEmailListResponse(
            emails=email_items,
            count=len(email_items),
            total=total,
            test_info={
                "user_id": test_user_id,
                "org_id": test_org_id,
                "mode": "unauthenticated_test",
                "warning": "This endpoint bypasses authentication"
            }
        )
        
    except Exception as e:
        logger.error(f"[TEST] Failed to list emails: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list emails",
                "message": str(e),
                "test_info": {
                    "user_id": test_user_id,
                    "org_id": test_org_id
                }
            }
        )


@router.get("/emails/{email_id}", response_model=TestEmailDetailResponse)
async def test_get_email(
    email_id: str,
    request: Request,
    user_id: Optional[str] = Query(default=None, description="Override test user_id"),
    org_id: Optional[str] = Query(default=None, description="Override test org_id"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get email details for testing (NO AUTHENTICATION REQUIRED).
    
    Uses demo user/org by default, or custom user_id/org_id if provided.
    """
    test_user_id = user_id or DEMO_USER_ID
    test_org_id = org_id or DEMO_ORG_ID
    
    logger.info(f"[TEST] Getting email {email_id}: user_id={test_user_id}, org_id={test_org_id}")
    
    try:
        # Get email (with tenant isolation)
        query = select(Email).where(
            Email.id == email_id,
            Email.user_id == test_user_id,
            Email.org_id == test_org_id
        )
        
        result = await db.execute(query)
        email = result.scalar_one_or_none()
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Email not found",
                    "message": f"No email with id '{email_id}' found for user_id='{test_user_id}', org_id='{test_org_id}'",
                    "possible_reasons": [
                        "Email ID does not exist",
                        "Email belongs to a different user/org",
                        "No emails have been synced yet"
                    ],
                    "how_to_fix": [
                        "Check the email ID is correct",
                        "Try listing emails first with GET /api/v1/test/emails",
                        "Provide correct user_id/org_id query parameters"
                    ],
                    "test_info": {
                        "user_id": test_user_id,
                        "org_id": test_org_id
                    }
                }
            )
        
        return TestEmailDetailResponse(
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
            labels=email.labels,
            test_info={
                "user_id": test_user_id,
                "org_id": test_org_id,
                "mode": "unauthenticated_test",
                "warning": "This endpoint bypasses authentication"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TEST] Failed to get email: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get email",
                "message": str(e),
                "test_info": {
                    "user_id": test_user_id,
                    "org_id": test_org_id
                }
            }
        )


@router.post("/rag/query", response_model=TestRAGQueryResponse)
async def test_rag_query(
    request_body: TestRAGQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Execute RAG query for testing (NO AUTHENTICATION REQUIRED).
    
    Uses demo user/org by default, or custom user_id/org_id if provided in body.
    
    This endpoint:
    1. Generates query embedding
    2. Retrieves relevant email chunks from Pinecone
    3. Runs CrewAI agent pipeline
    4. Returns grounded answer with email citations
    """
    test_user_id = request_body.user_id or DEMO_USER_ID
    test_org_id = request_body.org_id or DEMO_ORG_ID
    request_id = getattr(request.state, "request_id", "test-request")
    
    logger.info(
        f"[TEST] RAG query: request_id={request_id}, user_id={test_user_id}, "
        f"query={request_body.query[:100]}"
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
            org_id=test_org_id,
            user_id=test_user_id,
            date_from=date_from,
            date_to=date_to,
            sender=sender,
            request_id=request_id
        )
        
        logger.info(f"[TEST] RAG query completed: request_id={request_id}")
        
        # Add test info to response
        return TestRAGQueryResponse(
            answer=result.answer,
            sources=[
                TestEmailSource(
                    email_id=s.email_id,
                    subject=s.subject,
                    sender=s.sender,
                    date=s.date,
                    relevance_score=s.relevance_score
                )
                for s in result.sources
            ],
            metadata=result.metadata,
            test_info={
                "user_id": test_user_id,
                "org_id": test_org_id,
                "mode": "unauthenticated_test",
                "warning": "This endpoint bypasses authentication"
            }
        )
        
    except Exception as e:
        logger.error(
            f"[TEST] RAG query failed: request_id={request_id}, error={e}",
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Query processing failed",
                "message": str(e),
                "request_id": request_id,
                "test_info": {
                    "user_id": test_user_id,
                    "org_id": test_org_id
                },
                "possible_reasons": [
                    "RAG service not configured",
                    "Pinecone connection failed",
                    "OpenAI API key missing",
                    "No emails indexed for this user/org"
                ],
                "how_to_fix": [
                    "Check environment variables are set",
                    "Verify Pinecone index exists",
                    "Sync some emails first"
                ]
            }
        )


@router.get("/emails/count/summary")
async def test_email_count(
    request: Request,
    user_id: Optional[str] = Query(default=None),
    org_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get email count summary for testing.
    
    Useful to check if any emails exist for the test user/org.
    """
    test_user_id = user_id or DEMO_USER_ID
    test_org_id = org_id or DEMO_ORG_ID
    
    try:
        # Count for test user/org
        count_query = select(func.count(Email.id)).where(
            Email.user_id == test_user_id,
            Email.org_id == test_org_id
        )
        result = await db.execute(count_query)
        user_count = result.scalar() or 0
        
        # Total count in system
        total_query = select(func.count(Email.id))
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0
        
        return {
            "test_user_email_count": user_count,
            "total_emails_in_system": total_count,
            "test_info": {
                "user_id": test_user_id,
                "org_id": test_org_id
            },
            "message": "No emails found for test user" if user_count == 0 else f"Found {user_count} emails"
        }
        
    except Exception as e:
        logger.error(f"[TEST] Failed to count emails: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to count emails",
                "message": str(e)
            }
        )


# ============== HTML UI Endpoints for Testing ==============

@router.get("/ui/emails", response_class=HTMLResponse)
async def test_email_list_ui(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = Query(default=None, description="Override test user_id"),
    org_id: Optional[str] = Query(default=None, description="Override test org_id"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Show email list page UI (NO AUTHENTICATION REQUIRED).
    
    Displays paginated list of emails in a user-friendly HTML page.
    Uses demo user/org by default, or custom user_id/org_id if provided.
    """
    test_user_id = user_id or DEMO_USER_ID
    test_org_id = org_id or DEMO_ORG_ID
    
    # Get total count
    count_query = select(func.count(Email.id)).where(
        Email.user_id == test_user_id,
        Email.org_id == test_org_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get emails
    query = (
        select(Email)
        .where(Email.user_id == test_user_id, Email.org_id == test_org_id)
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
        user_id=test_user_id,
        org_id=test_org_id,
        base_url="/api/v1/test/ui/emails",
        is_test=True
    )
    return HTMLResponse(content=html_content)


@router.get("/ui/emails/{email_id}", response_class=HTMLResponse)
async def test_email_detail_ui(
    email_id: str,
    request: Request,
    user_id: Optional[str] = Query(default=None, description="Override test user_id"),
    org_id: Optional[str] = Query(default=None, description="Override test org_id"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Show email detail page UI (NO AUTHENTICATION REQUIRED).
    
    Displays full email content in a user-friendly HTML page.
    Uses demo user/org by default, or custom user_id/org_id if provided.
    """
    test_user_id = user_id or DEMO_USER_ID
    test_org_id = org_id or DEMO_ORG_ID
    
    # Get email (with tenant isolation)
    query = select(Email).where(
        Email.id == email_id,
        Email.user_id == test_user_id,
        Email.org_id == test_org_id
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
    
    # Build back URL with query params
    back_url = f"/api/v1/test/ui/emails?user_id={test_user_id}&org_id={test_org_id}"
    
    html_content = get_email_detail_page(
        email=email_data,
        back_url=back_url,
        is_test=True
    )
    return HTMLResponse(content=html_content)
