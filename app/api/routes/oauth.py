"""
OAuth API Routes
Google OAuth authentication flow
"""
import logging
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_async_db
from app.models.user import User
from app.services.token_service import get_token_service

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory state storage (use Redis in production)
_oauth_states: dict = {}


@router.get("/start")
async def oauth_start():
    """
    Get Google OAuth URL.
    
    Returns the OAuth URL - open it in your browser to authenticate with Google.
    Do NOT use "Try it out" in Swagger - copy the oauth_url and paste in a new browser tab.
    """
    # Generate secure state token to prevent CSRF
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created_at": datetime.now(timezone.utc)
    }
    
    # Build OAuth URL
    oauth_params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(settings.GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }
    
    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(oauth_params)}"
    
    logger.info(f"Initiating Google OAuth flow, state={state[:8]}...")
    
    return {
        "message": "InboxMind OAuth",
        "oauth_url": oauth_url,
        "instructions": "Open the oauth_url in your browser (copy and paste into a new tab)"
    }


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
    stores encrypted tokens, and redirects to email list.
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
            await db.flush()
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
            "user_id": str(user.id),
            "email": user.email,
            "org_id": user.org_id
        }
    )
    
    logger.info(f"OAuth flow completed for user {user.id}")
    
    # Return success UI page with Bearer token
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>InboxMind - Authentication Successful</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 2.5rem;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                width: 90%;
            }}
            h1 {{ color: #28a745; margin-bottom: 1rem; }}
            .success {{ background: #d4edda; border-left: 4px solid #28a745; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            .info {{ background: #e7f3ff; border-left: 4px solid #1a73e8; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            .token-box {{
                background: #1a1a2e;
                color: #60a5fa;
                padding: 15px;
                border-radius: 8px;
                word-break: break-all;
                font-family: monospace;
                font-size: 12px;
                margin: 15px 0;
            }}
            .btn {{
                background: #3b82f6;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                margin: 5px;
                text-decoration: none;
                display: inline-block;
            }}
            .btn:hover {{ background: #2563eb; }}
            code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 Authentication Successful!</h1>
            
            <div class="success">
                <strong>✓ Connected as:</strong> {user.email}
            </div>
            
            <div class="info">
                <strong>Your Credentials:</strong><br>
                <strong>User ID:</strong> <code>{user.id}</code><br>
                <strong>Org ID:</strong> <code>{user.org_id}</code>
            </div>
            
            <h3>🔑 Your Access Token</h3>
            <p>Use this Bearer token for API requests:</p>
            <div class="token-box" id="token">{app_token}</div>
            
            <button class="btn" onclick="navigator.clipboard.writeText(document.getElementById('token').textContent).then(() => {{ this.textContent = '✓ Copied!'; setTimeout(() => this.textContent = '📋 Copy Token', 2000); }})">
                📋 Copy Token
            </button>
            <a href="/docs" class="btn">📚 API Docs</a>
            
            <h3 style="margin-top: 25px;">Next Steps</h3>
            <ul>
                <li>Use the token in header: <code>Authorization: Bearer &lt;token&gt;</code></li>
                <li>Get emails: <code>GET /api/v1/emails</code></li>
                <li>Query with AI: <code>POST /api/v1/rag/query</code></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
