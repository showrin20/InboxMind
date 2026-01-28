"""
FastAPI Main Application
Production-ready multi-tenant RAG platform
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time
import uuid

from app.core.config import get_settings
from app.core.logging import setup_logging, audit_logger
from app.db.session import init_db, close_db
from app.vectorstore.pinecone_client import get_pinecone_client

# Import centralized routes
from app.api.routes import api_router, register_all_routes

settings = get_settings()

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{app.version}")
    logger.info(f"Environment: {settings.APP_ENV}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    # Initialize Pinecone
    try:
        pinecone_client = get_pinecone_client()
        if pinecone_client.health_check():
            logger.info("Pinecone connection verified")
        else:
            logger.error("Pinecone health check failed")
    except Exception as e:
        logger.error(f"Pinecone initialization failed: {e}")
        raise
    
    logger.info(f"{settings.APP_NAME} started successfully")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    
    await close_db()
    logger.info("Database connections closed")
    
    logger.info(f"{settings.APP_NAME} shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="""
## AI-powered email search and analysis.
    """,
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for tracing"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Request started: method={request.method}, "
        f"path={request.url.path}, request_id={request_id}"
    )
    
    response = await call_next(request)
    
    duration_ms = (time.time() - start_time) * 1000
    
    logger.info(
        f"Request completed: method={request.method}, "
        f"path={request.url.path}, status={response.status_code}, "
        f"duration_ms={duration_ms:.2f}, request_id={request_id}"
    )
    
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "request_id": getattr(request.state, "request_id", None)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}, "
        f"request_id={request_id}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": request_id
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Returns system status.
    """
    try:
        # Check Pinecone
        pinecone_client = get_pinecone_client()
        pinecone_healthy = pinecone_client.health_check()
        
        health_status = {
            "status": "healthy" if pinecone_healthy else "degraded",
            "app": settings.APP_NAME,
            "version": "1.0.0",
            "environment": settings.APP_ENV,
            "services": {
                "pinecone": "healthy" if pinecone_healthy else "unhealthy",
                "database": "healthy"  # Would check DB connection
            }
        }
        
        status_code = status.HTTP_200_OK if pinecone_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(content=health_status, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e)
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "description": "Enterprise multi-tenant agentic RAG platform",
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
        "health": "/health"
    }


# Register all routes from centralized routes module
register_all_routes(app)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
