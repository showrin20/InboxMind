"""
Auth API Routes
Simple authentication for development/testing

## How to Authenticate

1. **Register or Login** to get an access token:
   - POST /api/v1/auth/register {"email": "you@example.com", "password": "yourpassword"}
   - POST /api/v1/auth/login {"email": "you@example.com", "password": "yourpassword"}

2. **Use the token** in subsequent requests:
   - Add header: `Authorization: Bearer <your_access_token>`

3. **Example with curl**:
   ```
   curl -X GET http://localhost:8000/api/v1/emails \\
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
   ```
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import JWTManager, PasswordManager, get_current_user
from app.db.session import get_async_db
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()
jwt_manager = JWTManager()
password_manager = PasswordManager()


class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Register request - email and password only"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Token response - use this token for authenticated requests.
    
    Add to your requests as: Authorization: Bearer <access_token>
    """
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    usage_example: str = "Add header 'Authorization: Bearer <access_token>' to your requests"


class AuthHelpResponse(BaseModel):
    """Authentication help"""
    message: str
    steps: list
    example_curl: str


@router.get("/help", response_model=AuthHelpResponse)
async def auth_help():
    """
    Get help on how to authenticate with the API.
    
    Returns step-by-step instructions for getting and using access tokens.
    """
    return AuthHelpResponse(
        message="How to authenticate with InboxMind API",
        steps=[
            "1. Register: POST /api/v1/auth/register with {\"email\": \"you@example.com\", \"password\": \"secret\"}",
            "2. Copy the 'access_token' from the response",
            "3. Add header to all requests: Authorization: Bearer <your_token>",
            "4. Connect Gmail: GET /api/v1/oauth/google",
            "5. Sync emails: POST /api/v1/emails/sync",
            "6. Query emails: POST /api/v1/rag/query"
        ],
        example_curl="curl -X GET http://localhost:8000/api/v1/emails -H \"Authorization: Bearer YOUR_TOKEN_HERE\""
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Register a new user account.
    
    For development/testing purposes.
    """
    # Check if user already exists
    existing = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with default org_id derived from email domain
    email_domain = request.email.split('@')[1] if '@' in request.email else 'default'
    user = User(
        email=request.email,
        org_id=email_domain,
        hashed_password=password_manager.hash_password(request.password),
        is_active=True,
        email_sync_enabled=True
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create JWT token
    token = jwt_manager.create_access_token({
        "sub": str(user.id),
        "user_id": str(user.id),
        "org_id": user.org_id,
        "email": user.email
    })
    
    logger.info(f"User registered: {user.email}")
    
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Login with email and password.
    
    Returns a JWT access token for API authentication.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not user.hashed_password or not password_manager.verify_password(
        request.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Create JWT token
    token = jwt_manager.create_access_token({
        "sub": str(user.id),
        "user_id": str(user.id),
        "org_id": user.org_id,
        "email": user.email
    })
    
    logger.info(f"User logged in: {user.email}")
    
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email
    )


class UserProfileResponse(BaseModel):
    """User profile response"""
    id: str
    email: str
    org_id: str
    full_name: Optional[str] = None
    is_active: bool
    gmail_connected: bool
    email_sync_enabled: bool


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user's profile.
    
    **Requires**: Authorization header with Bearer token.
    
    Example:
    ```
    curl -X GET http://localhost:8000/api/v1/auth/me \\
      -H "Authorization: Bearer <your_token>"
    ```
    """
    user = await get_current_user(request, db)
    
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        org_id=user.org_id,
        full_name=user.full_name,
        is_active=user.is_active,
        gmail_connected=bool(user.encrypted_access_token),
        email_sync_enabled=user.email_sync_enabled
    )
