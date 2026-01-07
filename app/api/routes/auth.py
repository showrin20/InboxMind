"""
Auth API Routes
Simple authentication for development/testing
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import JWTManager, PasswordManager
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
    """Register request"""
    email: EmailStr
    password: str
    org_id: str = "default"


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


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
    
    # Create user
    user = User(
        email=request.email,
        org_id=request.org_id,
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


@router.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current user info.
    
    This is a public endpoint that returns user info from a token.
    Pass Authorization: Bearer <token> header.
    """
    from fastapi import Request
    from app.core.security import get_current_user
    
    # This will be called from the route, we need request context
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Use /api/v1/auth/profile instead"
    )
