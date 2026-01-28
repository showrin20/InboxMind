"""Routes package"""

from app.api.routes.routes import (
    api_router,
    register_all_routes,
)

from app.api.routes.dependencies import (
    require_auth,
    AuthenticatedUser,
    get_current_user_from_request,
    get_db_from_request,
)

__all__ = [
    "api_router",
    "register_all_routes",
    "require_auth",
    "AuthenticatedUser",
    "get_current_user_from_request",
    "get_db_from_request",
]
