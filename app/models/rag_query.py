"""
RAG Query Model
Stores user queries and responses for audit trail
"""
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Index, ForeignKey, Boolean

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDMixin


class RAGQuery(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """
    RAG query audit log.
    Stores every query, response, and sources for compliance.
    """
    
    __tablename__ = "rag_queries"
    
    # Query information
    query_text = Column(
        Text,
        nullable=False,
        comment="User's query text"
    )
    
    # Filters applied
    filter_date_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date filter: from"
    )
    
    filter_date_to = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date filter: to"
    )
    
    filter_sender = Column(
        String(255),
        nullable=True,
        comment="Sender filter"
    )
    
    filter_keywords = Column(
        Text,
        nullable=True,
        comment="Additional keyword filters (JSON array)"
    )
    
    # Response
    answer_text = Column(
        Text,
        nullable=False,
        comment="Generated answer from AnswerAgent"
    )
    
    sources_json = Column(
        Text,
        nullable=True,
        comment="Source citations (JSON array of email metadata)"
    )
    
    # Performance metrics
    retrieval_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of vectors retrieved"
    )
    
    context_token_count = Column(
        Integer,
        nullable=True,
        comment="Total tokens in context"
    )
    
    processing_time_ms = Column(
        Float,
        nullable=True,
        comment="Total processing time in milliseconds"
    )
    
    # Agent execution tracking
    retriever_agent_time_ms = Column(Float, nullable=True)
    context_agent_time_ms = Column(Float, nullable=True)
    analyst_agent_time_ms = Column(Float, nullable=True)
    compliance_agent_time_ms = Column(Float, nullable=True)
    answer_agent_time_ms = Column(Float, nullable=True)
    
    # Quality & compliance
    answer_grounded = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether answer is grounded in retrieved context"
    )
    
    compliance_flags = Column(
        Text,
        nullable=True,
        comment="Compliance flags raised by ComplianceAgent (JSON array)"
    )
    
    pii_redacted = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether PII was redacted from response"
    )
    
    # Request metadata
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Request tracing ID"
    )
    
    user_agent = Column(
        String(255),
        nullable=True,
        comment="Client user agent"
    )
    
    ip_address = Column(
        String(45),
        nullable=True,
        comment="Client IP address (for security audit)"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_rag_query_tenant_date", "org_id", "user_id", "created_at"),
        Index("idx_rag_query_request", "request_id"),
    )
    
    def __repr__(self) -> str:
        return f"<RAGQuery(id={self.id}, query={self.query_text[:50]}, user_id={self.user_id})>"
