"""
Vector Record Model
Tracks embeddings stored in Pinecone for auditability
"""
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Index, ForeignKey

from app.db.base import Base, TimestampMixin, TenantMixin, UUIDMixin


class VectorRecord(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """
    Tracking table for vector embeddings stored in Pinecone.
    Provides audit trail and metadata for vector store operations.
    """
    
    __tablename__ = "vector_records"
    
    # Pinecone identifiers
    vector_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Pinecone vector ID (UUID)"
    )
    
    namespace = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Pinecone namespace (org_{org_id}_user_{user_id})"
    )
    
    # Source email
    email_id = Column(
        String(36),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source email ID"
    )
    
    # Chunk information
    chunk_index = Column(
        Integer,
        nullable=False,
        comment="Chunk number for this email (0-indexed)"
    )
    
    chunk_text = Column(
        Text,
        nullable=False,
        comment="Text content of this chunk"
    )
    
    chunk_token_count = Column(
        Integer,
        nullable=True,
        comment="Token count of chunk"
    )
    
    # Embedding metadata
    embedding_model = Column(
        String(100),
        nullable=False,
        comment="Embedding model used (e.g., text-embedding-3-small)"
    )
    
    embedding_dimension = Column(
        Integer,
        nullable=False,
        comment="Embedding vector dimension (should be 1536)"
    )
    
    # Status tracking
    pinecone_upserted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When vector was uploaded to Pinecone"
    )
    
    pinecone_verified = Column(
        String(10),
        default="false",
        nullable=False,
        comment="Whether vector exists in Pinecone (verified)"
    )
    
    # Additional metadata (JSON stored as text)
    metadata_json = Column(
        Text,
        nullable=True,
        comment="Additional metadata stored with vector (JSON)"
    )
    
    # Relationships
    # email = relationship("Email", back_populates="vector_records")
    
    # Indexes
    __table_args__ = (
        Index("idx_vector_email", "email_id", "chunk_index"),
        Index("idx_vector_namespace", "namespace"),
        Index("idx_vector_tenant", "org_id", "user_id"),
    )
    
    def __repr__(self) -> str:
        return f"<VectorRecord(id={self.id}, vector_id={self.vector_id}, email_id={self.email_id})>"
