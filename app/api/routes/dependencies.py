"""
Authentication Dependencies
Centralized authentication for all protected routes.

This module provides the single source of truth for authentication.
Authentication is applied at the router level in routes.py.
"""
import logging
from typing import Annotated, Optional

from fastapi import Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import JWTManager
from app.db.session import get_async_db
from app.models.user import User

logger = logging.getLogger(__name__)

# Central security scheme - this creates the single Authorize button in Swagger
security = HTTPBearer(
    scheme_name="Bearer",
    description="Enter your JWT token from /auth/register or /auth/login",
    auto_error=True
)

jwt_manager = JWTManager()


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """
    Centralized authentication dependency.
    
    Applied at the router level for all protected routes.
    Stores the authenticated user in request.state.user for access in endpoints.
    
    Returns:
        User: The authenticated user object
        
    Raises:
        HTTPException 401: If no token or invalid token
        HTTPException 403: If user is inactive
        HTTPException 404: If user not found
    """
    token = credentials.credentials
    
    # Decode and validate token
    payload = jwt_manager.decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Invalid or expired token",
                "message": "The provided JWT token is invalid, malformed, or has expired.",
                "how_to_fix": "Obtain a new token by logging in again",
                "get_token": "POST /api/v1/auth/login with email and password"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Invalid token payload",
                "message": "Token does not contain required user information.",
                "how_to_fix": "Please login again to get a new token.",
                "get_token": "POST /api/v1/auth/login with email and password"
            }
        )
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "User not found",
                "message": "The user associated with this token no longer exists.",
                "how_to_fix": "Register a new account or contact support.",
                "register": "POST /api/v1/auth/register"
            }
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Account inactive",
                "message": "Your user account has been deactivated.",
                "how_to_fix": "Contact your administrator to reactivate your account."
            }
        )
    
    # Store user and db in request state for access in endpoints
    request.state.user = user
    request.state.db = db
    return user


def get_current_user_from_request(request: Request) -> User:
    """
    Get the authenticated user from request state.
    
    Use this in endpoints to access the user after router-level authentication.
    
    Usage:
        @router.get("/protected")
        async def protected_route(request: Request):
            user = get_current_user_from_request(request)
            return {"user_id": user.id}
    """
    return request.state.user


def get_db_from_request(request: Request) -> AsyncSession:
    """Get database session from request state."""
    return request.state.db


# Type alias for cleaner dependency injection
AuthenticatedUser = Annotated[User, Depends(require_auth)]
