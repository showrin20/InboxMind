"""
SQLAlchemy declarative base and common mixins
"""
from datetime import datetime
from typing import Any
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy.sql import func
import uuid


Base = declarative_base()


class TimestampMixin:
    """
    Mixin for created_at and updated_at timestamps.
    Automatically managed by SQLAlchemy.
    """
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )


class TenantMixin:
    """
    Mixin for multi-tenant isolation.
    Every model must have org_id for tenant isolation.
    """
    
    org_id = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Organization ID for tenant isolation"
    )
    
    user_id = Column(
        String(50),
        nullable=False,
        index=True,
        comment="User ID within the organization"
    )


class UUIDMixin:
    """
    Mixin for UUID primary keys.
    Uses UUID4 for global uniqueness.
    """
    
    @declared_attr
    def id(cls):
        return Column(
            String(36),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
            comment="UUID primary key"
        )


def generate_uuid() -> str:
    """Generate a UUID4 string"""
    return str(uuid.uuid4())
