"""Database models package"""

# Import all models here so Alembic can detect them
from app.models.user import User
from app.models.email import Email
from app.models.audit_log import AuditLog
from app.models.rag_query import RAGQuery
from app.models.vector_record import VectorRecord

__all__ = [
    "User",
    "Email",
    "AuditLog",
    "RAGQuery",
    "VectorRecord",
]
