"""
Embedding schemas and data models
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EmbeddingChunk(BaseModel):
    """
    Represents a text chunk with its embedding and metadata.
    """
    chunk_text: str = Field(description="Text content of the chunk")
    chunk_index: int = Field(description="Index of chunk within source document")
    token_count: int = Field(description="Token count of chunk")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_text": "Meeting scheduled for tomorrow at 10 AM...",
                "chunk_index": 0,
                "token_count": 45
            }
        }


class EmailEmbedding(BaseModel):
    """
    Complete embedding data for an email.
    """
    email_id: str
    chunks: List[EmbeddingChunk]
    embedding_model: str
    dimension: int
    total_tokens: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "email_id": "abc-123",
                "chunks": [],
                "embedding_model": "text-embedding-3-small",
                "dimension": 1536,
                "total_tokens": 250
            }
        }


class VectorUpsertRecord(BaseModel):
    """
    Record for upserting to Pinecone.
    """
    vector_id: str = Field(description="Unique vector ID (UUID)")
    embedding: List[float] = Field(description="Embedding vector")
    metadata: Dict[str, Any] = Field(description="Metadata for filtering")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vector_id": "vec_abc123_0",
                "embedding": [0.1, 0.2, 0.3],
                "metadata": {
                    "email_id": "abc123",
                    "org_id": "org1",
                    "user_id": "user1"
                }
            }
        }
