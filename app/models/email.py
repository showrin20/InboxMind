"""
Email Model
Stores email metadata and content
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Index, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDMixin


class Email(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """
    Email metadata and content storage.
    Full email content stored for RAG context reconstruction.
    """
    
    __tablename__ = "emails"
    
    # Email identification
    message_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Email Message-ID header (unique per provider)"
    )
    
    thread_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Email thread/conversation ID"
    )
    
    # Email metadata
    subject = Column(
        Text,
        nullable=True,
        comment="Email subject line"
    )
    
    sender = Column(
        String(255),
        nullable=False,
        index=True,
        comment="From email address"
    )
    
    sender_name = Column(
        String(255),
        nullable=True,
        comment="Sender's display name"
    )
    
    recipients_to = Column(
        Text,
        nullable=True,
        comment="To recipients (comma-separated)"
    )
    
    recipients_cc = Column(
        Text,
        nullable=True,
        comment="CC recipients (comma-separated)"
    )
    
    recipients_bcc = Column(
        Text,
        nullable=True,
        comment="BCC recipients (comma-separated)"
    )
    
    # Timestamps
    sent_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When email was sent (from Date header)"
    )
    
    received_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="When we ingested this email"
    )
    
    # Content
    body_text = Column(
        Text,
        nullable=True,
        comment="Plain text email body"
    )
    
    body_html = Column(
        Text,
        nullable=True,
        comment="HTML email body"
    )
    
    # Attachments
    has_attachments = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether email has attachments"
    )
    
    attachment_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of attachments"
    )
    
    # Classification
    labels = Column(
        Text,
        nullable=True,
        comment="Email labels/categories (comma-separated)"
    )
    
    is_important = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Marked as important"
    )
    
    is_read = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Read status"
    )
    
    # Vector embedding status
    is_embedded = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether embeddings have been generated"
    )
    
    embedding_generated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When embeddings were created"
    )
    
    # Provider-specific
    provider = Column(
        String(50),
        nullable=False,
        comment="Email provider: 'google' or 'microsoft'"
    )
    
    provider_message_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Provider's internal message ID"
    )
    
    raw_headers = Column(
        Text,
        nullable=True,
        comment="Raw email headers (JSON)"
    )
    
    # Relationships
    # vector_records = relationship("VectorRecord", back_populates="email", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_email_tenant_sender", "org_id", "user_id", "sender"),
        Index("idx_email_tenant_date", "org_id", "user_id", "sent_at"),
        Index("idx_email_thread", "thread_id"),
        Index("idx_email_embedding_status", "is_embedded", "org_id", "user_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Email(id={self.id}, subject={self.subject[:50]}, sender={self.sender})>"
    
    @property
    def text_content(self) -> str:
        """Get best available text content"""
        return self.body_text or self.body_html or ""
    
    def to_metadata_dict(self) -> dict:
        """
        Generate metadata dict for vector storage.
        This metadata is stored with each embedding chunk.
        """
        return {
            "email_id": self.id,
            "message_id": self.message_id,
            "thread_id": self.thread_id or "",
            "subject": self.subject or "",
            "sender": self.sender,
            "sender_name": self.sender_name or "",
            "sent_at": self.sent_at.isoformat() if self.sent_at else "",
            "org_id": self.org_id,
            "user_id": self.user_id,
            "provider": self.provider,
            "has_attachments": self.has_attachments,
            "labels": self.labels or "",
        }
