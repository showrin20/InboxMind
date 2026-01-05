"""
Audit Log Model
Comprehensive audit trail for compliance and security
"""
from sqlalchemy import Column, String, Text, DateTime, Index

from app.db.base import Base, TimestampMixin, UUIDMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """
    Comprehensive audit log for all sensitive operations.
    Required for SOC 2, GDPR, and enterprise compliance.
    """
    
    __tablename__ = "audit_logs"
    
    # Event classification
    event_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Event type: oauth_event, rag_query, email_access, data_deletion, security_event"
    )
    
    event_category = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Category: authentication, data_access, modification, deletion, security"
    )
    
    severity = Column(
        String(20),
        nullable=False,
        comment="Severity: info, warning, error, critical"
    )
    
    # Actor
    user_id = Column(
        String(50),
        nullable=True,
        index=True,
        comment="User who performed the action"
    )
    
    org_id = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Organization context"
    )
    
    # Action details
    action = Column(
        String(255),
        nullable=False,
        comment="Specific action performed"
    )
    
    resource_type = Column(
        String(100),
        nullable=True,
        comment="Type of resource affected: email, vector, query, user"
    )
    
    resource_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="ID of affected resource"
    )
    
    # Request context
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Request tracing ID"
    )
    
    ip_address = Column(
        String(45),
        nullable=True,
        comment="Client IP address"
    )
    
    user_agent = Column(
        String(255),
        nullable=True,
        comment="Client user agent"
    )
    
    # Outcome
    success = Column(
        String(10),
        nullable=False,
        comment="Whether action succeeded (true/false)"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if action failed"
    )
    
    # Details
    details_json = Column(
        Text,
        nullable=True,
        comment="Additional context (JSON) - sanitized, no sensitive data"
    )
    
    # Compliance
    retention_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this log can be deleted (for retention policies)"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_event_type", "event_type", "created_at"),
        Index("idx_audit_user", "user_id", "created_at"),
        Index("idx_audit_org", "org_id", "created_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_severity", "severity", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, action={self.action})>"
