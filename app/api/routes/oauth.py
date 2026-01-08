"""
OAuth API Routes
Google OAuth authentication flow
"""
import logging
import secrets
from typing import Optional
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_async_db
from app.models.user import User
from app.services.token_service import get_token_service
from app.ui import get_connect_gmail_page, get_oauth_success_page

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()


# In-memory state storage (use Redis in production)
_oauth_states: dict = {}


class TokenResponse(BaseModel):
    """OAuth token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str


class UserInfoResponse(BaseModel):
    """User info response"""
    id: str
    email: str
    full_name: Optional[str] = None
    oauth_provider: str
    is_active: bool
    email_sync_enabled: bool
    last_email_sync: Optional[datetime] = None


@router.get("/google", response_class=HTMLResponse)
async def google_oauth_init(request: Request):
    """
    Show Gmail connection UI page.
    
    Displays a page explaining the OAuth flow and a button to start it.
    """
    html_content = get_connect_gmail_page(
        oauth_start_url="/api/v1/oauth/google/start",
        is_test=False,
        is_connected=False
    )
    return HTMLResponse(content=html_content)


@router.get("/google/start")
async def google_oauth_start(request: Request):
    """
    Initiate Google OAuth flow.
    
    Redirects the user to Google's OAuth consent screen.
    After consent, Google will redirect back to /oauth/google/callback.
    """
    # Generate secure state token to prevent CSRF
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created_at": datetime.now(timezone.utc),
        "request_id": getattr(request.state, "request_id", None)
    }
    
    # Build OAuth URL
    oauth_params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(settings.GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",  # Request refresh token
        "prompt": "consent"  # Force consent to get refresh token
    }
    
    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(oauth_params)}"
    
    logger.info(f"Initiating Google OAuth flow, state={state[:8]}...")
    
    return RedirectResponse(url=oauth_url)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle Google OAuth callback.
    
    Exchanges authorization code for tokens, creates/updates user,
    and stores encrypted tokens.
    """
    import aiohttp
    
    # Verify state token
    if state not in _oauth_states:
        logger.warning(f"Invalid OAuth state token: {state[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state token. Please try again."
        )
    
    # Remove used state
    del _oauth_states[state]
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=token_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token exchange failed: {error_text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to exchange authorization code"
                    )
                
                tokens = await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Token exchange request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to communicate with Google"
        )
    
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    
    if not refresh_token:
        logger.warning("No refresh token received - user may have already granted access")
    
    # Get user info from Google
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(userinfo_url, headers=headers) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to get user info from Google"
                    )
                
                user_info = await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"User info request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to communicate with Google"
        )
    
    google_id = user_info["id"]
    email = user_info["email"]
    full_name = user_info.get("name")
    
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
        # Update existing user
        logger.info(f"Existing user logged in: {email}")
        user.full_name = full_name
    else:
        # Check if email already exists (account linking scenario)
        result = await db.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Link Google to existing account
            user = existing_user
            user.oauth_provider = "google"
            user.oauth_provider_id = google_id
            user.full_name = full_name or user.full_name
            logger.info(f"Linked Google account to existing user: {email}")
        else:
            # Create new user
            # Generate org_id for demo (in production, this would come from signup flow)
            org_id = f"org_{secrets.token_hex(8)}"
            
            user = User(
                email=email,
                org_id=org_id,
                full_name=full_name,
                oauth_provider="google",
                oauth_provider_id=google_id,
                is_active=True,
                email_sync_enabled=True
            )
            db.add(user)
            await db.flush()  # Get user.id
            logger.info(f"Created new user: {email}")
    
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
        # Only update access token if no refresh token
        user.encrypted_access_token = token_service.encrypt_token(access_token)
        user.token_expires_at = datetime.now(timezone.utc) + __import__('datetime').timedelta(seconds=expires_in)
        await db.commit()
    
    await db.refresh(user)
    
    # Create app JWT token
    from app.core.security import create_access_token
    
    app_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "org_id": user.org_id
        }
    )
    
    logger.info(f"OAuth flow completed for user {user.id}")
    
    # Return success UI page with link to email list
    html_content = get_oauth_success_page(
        user_email=user.email,
        user_id=str(user.id),
        org_id=user.org_id,
        synced_count=0,
        emails_url="/api/v1/emails/ui/list",
        is_test=False
    )
    return HTMLResponse(content=html_content)


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user info.
    
    Requires valid JWT token in Authorization header.
    """
    from app.core.security import get_current_user_id
    
    # Get user ID from JWT
    try:
        user_id = await get_current_user_id(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication"
        )
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserInfoResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        oauth_provider=user.oauth_provider or "",
        is_active=user.is_active,
        email_sync_enabled=user.email_sync_enabled,
        last_email_sync=user.last_email_sync
    )


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Logout user and revoke OAuth tokens.
    """
    from app.core.security import get_current_user_id
    
    try:
        user_id = await get_current_user_id(request)
    except Exception:
        # Already logged out or invalid token
        return {"message": "Logged out"}
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Revoke OAuth tokens
        token_service = get_token_service()
        await token_service.revoke_tokens(db, user)
    
    logger.info(f"User logged out: {user_id}")
    
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Refresh the application JWT token.
    
    Also refreshes the OAuth token if needed.
    """
    from app.core.security import get_current_user_id, create_access_token
    
    try:
        user_id = await get_current_user_id(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Ensure OAuth token is valid (refreshes if needed)
    token_service = get_token_service()
    await token_service.get_valid_access_token(db, user)
    
    # Create new app token
    app_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "org_id": user.org_id
        }
    )
    
    return TokenResponse(
        access_token=app_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=str(user.id),
        email=user.email
    )
