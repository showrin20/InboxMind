"""
Enterprise Configuration Management
Multi-tenant settings with strict validation
"""
from typing import List, Optional
from pydantic import Field, validator, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    """
    Production-grade configuration with environment variable loading.
    All sensitive values loaded from environment, never hardcoded.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "InboxMind"
    APP_ENV: str = Field(default="production", pattern="^(development|staging|production)$")
    DEBUG: bool = False
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = Field(
        description="PostgreSQL connection string for production, SQLite for local dev"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_ECHO: bool = False
    
    # Pinecone Vector Database
    PINECONE_API_KEY: str = Field(min_length=20)
    PINECONE_ENVIRONMENT: str = "gcp-starter"
    PINECONE_INDEX_NAME: str = "email-rag-prod"
    PINECONE_DIMENSION: int = 1536
    PINECONE_METRIC: str = Field(default="cosine", pattern="^(cosine|euclidean|dotproduct)$")
    PINECONE_NAMESPACE_PREFIX: str = "org"  # org_{org_id}_user_{user_id}
    
    # Google Gemini
    GEMINI_API_KEY: Optional[str] = Field(default=None, min_length=20)
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
    GEMINI_MAX_TOKENS: int = 4096
    GEMINI_TEMPERATURE: float = 0.2  # Lower for factual RAG responses
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_SCOPES: List[str] = Field(
        default=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]
    )
    
    # Token Encryption
    FERNET_KEY: str = Field(
        description="Fernet key for encrypting OAuth tokens at rest. Generate with Fernet.generate_key()"
    )
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Background Jobs
    EMAIL_SYNC_INTERVAL_MINUTES: int = 15
    EMBEDDING_BATCH_SIZE: int = 50
    MAX_CONCURRENT_JOBS: int = 10
    
    # CrewAI Configuration
    CREWAI_VERBOSE: bool = True
    MAX_RETRIEVAL_RESULTS: int = 20
    CONTEXT_WINDOW_SIZE: int = 10000
    MIN_RELEVANCE_SCORE: float = 0.7
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    
    # Security
    TOKEN_REFRESH_BUFFER_SECONDS: int = 300  # Refresh tokens 5 min before expiry
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    
    # Compliance
    PII_REDACTION_ENABLED: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 365
    
    @validator("SECRET_KEY", pre=True)
    def validate_secret_key(cls, v: str) -> str:
        """Ensure SECRET_KEY is strong enough for production"""
        if v == "your-secret-key-min-32-chars-change-in-production":
            if cls.model_fields.get("APP_ENV", "production") == "production":
                raise ValueError("Must set a secure SECRET_KEY in production")
            # Generate a random key for development
            return secrets.token_urlsafe(32)
        return v
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.APP_ENV == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.APP_ENV == "development"
    
    def get_namespace(self, org_id: str, user_id: str) -> str:
        """
        Generate Pinecone namespace for tenant isolation.
        Format: org_{org_id}_user_{user_id}
        """
        return f"{self.PINECONE_NAMESPACE_PREFIX}_{org_id}_user_{user_id}"
    
    def get_database_url(self, async_driver: bool = True) -> str:
        """
        Get database URL with appropriate driver.
        Production: PostgreSQL with asyncpg (async) or psycopg2 (sync)
        Development: Can use SQLite with aiosqlite (async) or sqlite3 (sync)
        
        Args:
            async_driver: If True, returns async driver URL. If False, returns sync driver URL.
        """
        url = self.DATABASE_URL
        
        if async_driver:
            # Convert to async drivers
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
            elif url.startswith("sqlite:///"):
                url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        else:
            # Convert to sync drivers (for Alembic migrations)
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
            elif url.startswith("sqlite+aiosqlite:///"):
                url = url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
            elif url.startswith("postgresql://"):
                # Already sync, leave as is (uses psycopg2 by default)
                pass
        
        return url


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance.
    Use this function throughout the application to access configuration.
    """
    return Settings()


# Convenience export
settings = get_settings()
