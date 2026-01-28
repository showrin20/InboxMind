"""
Routes Aggregator
Central module that combines all API routes into a single router.

This module provides a clean way to include all routes in the main application
without importing each router individually.

Authentication is handled centrally at the router level via dependencies.
"""
import logging

from fastapi import APIRouter, Depends

from app.core.config import get_settings

# Import routers directly from files to avoid circular imports
from app.api.routes.oauth import router as oauth_router
from app.api.routes.rag import router as rag_router
from app.api.routes.emails import router as emails_router

# Import authentication dependency
from app.api.routes.dependencies import require_auth, AuthenticatedUser

settings = get_settings()
logger = logging.getLogger(__name__)


def register_all_routes(app) -> None:
    """
    Register all routes to the FastAPI application.
    
    Authentication is applied centrally:
    - OAuth routes: Public (OAuth flow handles its own authentication)
    - Protected routes (rag, emails): require_auth dependency applied at router level
    
    Args:
        app: FastAPI application instance
    """
    # OAuth routes - public (OAuth flow handles its own authentication)
    app.include_router(
        oauth_router, 
        prefix=f"{settings.API_V1_PREFIX}/oauth", 
        tags=["OAuth"]
    )
    app.include_router(
        rag_router, 
        prefix=f"{settings.API_V1_PREFIX}/rag", 
        tags=["RAG"],
        dependencies=[Depends(require_auth)]
    )
    app.include_router(
        emails_router, 
        prefix=f"{settings.API_V1_PREFIX}/emails", 
        tags=["Emails"],
        dependencies=[Depends(require_auth)]
    )


# =============================================================================
# COMBINED API ROUTER (alternative usage)
# =============================================================================

# Create a combined API router for all v1 routes
api_router = APIRouter()

# OAuth routes - public (OAuth flow handles its own authentication)
api_router.include_router(
    oauth_router, 
    prefix="/oauth", 
    tags=["OAuth"]
)
api_router.include_router(
    rag_router, 
    prefix="/rag", 
    tags=["RAG"],
    dependencies=[Depends(require_auth)]
)
api_router.include_router(
    emails_router, 
    prefix="/emails", 
    tags=["Emails"],
    dependencies=[Depends(require_auth)]
)
