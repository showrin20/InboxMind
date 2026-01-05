"""
User Model
Stores user account information and OAuth configuration
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """
    User account model.
    Stores authentication info and OAuth provider configuration.
    """
    
    __tablename__ = "users"
    
    # User identification
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (unique)"
    )
    
    org_id = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Organization ID for multi-tenancy"
    )
    
    # Authentication
    hashed_password = Column(
        String(255),
        nullable=True,
        comment="Hashed password (may be null for OAuth-only users)"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Account active status"
    )
    
    is_superuser = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Admin privileges"
    )
    
    # Profile
    full_name = Column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    # OAuth Configuration
    oauth_provider = Column(
        String(50),
        nullable=True,
        comment="OAuth provider: 'google'"
    )
    
    oauth_provider_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Unique ID from OAuth provider"
    )
    
    # Encrypted OAuth tokens (NEVER store plaintext)
    encrypted_access_token = Column(
        Text,
        nullable=True,
        comment="Fernet-encrypted OAuth access token"
    )
    
    encrypted_refresh_token = Column(
        Text,
        nullable=True,
        comment="Fernet-encrypted OAuth refresh token"
    )
    
    token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="OAuth access token expiration time"
    )
    
    # Email sync configuration
    last_email_sync = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful email sync timestamp"
    )
    
    email_sync_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable automatic email syncing"
    )
    
    # Security
    failed_login_attempts = Column(
        String(10),
        default="0",
        nullable=False,
        comment="Failed login counter for rate limiting"
    )
    
    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Account lock expiration after too many failed logins"
    )
    
    # Relationships
    # emails = relationship("Email", back_populates="user", cascade="all, delete-orphan")
    # rag_queries = relationship("RAGQuery", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_user_org_email", "org_id", "email"),
        Index("idx_user_oauth", "oauth_provider", "oauth_provider_id"),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, org_id={self.org_id})>"
    
    def is_oauth_token_valid(self) -> bool:
        """Check if OAuth access token is still valid"""
        if not self.token_expires_at:
            return False
        return datetime.utcnow() < self.token_expires_at
    
    def is_account_locked(self) -> bool:
        """Check if account is temporarily locked"""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
