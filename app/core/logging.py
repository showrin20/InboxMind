"""
Structured Logging Configuration
JSON-formatted logs for production monitoring and audit trails
"""
import logging
import sys
from typing import Any, Dict
from datetime import datetime
import structlog
from pythonjsonlogger import jsonlogger

from app.core.config import get_settings

settings = get_settings()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON log formatter with additional context.
    Ensures all logs are structured and parseable.
    """
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['app'] = settings.APP_NAME
        log_record['env'] = settings.APP_ENV
        
        # Add context if present
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'org_id'):
            log_record['org_id'] = record.org_id
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    Uses JSON format in production, human-readable in development.
    """
    
    # Determine log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    if settings.is_production or settings.APP_ENV == "staging":
        # JSON format for production/staging
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.is_production else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Reduce noise from noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("pinecone").setLevel(logging.INFO)
    
    root_logger.info(
        f"Logging configured: level={settings.LOG_LEVEL}, env={settings.APP_ENV}"
    )


class AuditLogger:
    """
    Dedicated audit logger for compliance and security events.
    Logs all RAG queries, data access, and authentication events.
    """
    
    def __init__(self):
        self.logger = structlog.get_logger("audit")
    
    def log_rag_query(
        self,
        user_id: str,
        org_id: str,
        query: str,
        filters: Dict[str, Any],
        result_count: int,
        processing_time_ms: float,
        request_id: str
    ) -> None:
        """Log a RAG query for audit trail"""
        self.logger.info(
            "rag_query",
            user_id=user_id,
            org_id=org_id,
            query=query,
            filters=filters,
            result_count=result_count,
            processing_time_ms=processing_time_ms,
            request_id=request_id
        )
    
    def log_email_access(
        self,
        user_id: str,
        org_id: str,
        email_id: str,
        action: str,
        request_id: str
    ) -> None:
        """Log email access for compliance"""
        self.logger.info(
            "email_access",
            user_id=user_id,
            org_id=org_id,
            email_id=email_id,
            action=action,
            request_id=request_id
        )
    
    def log_oauth_event(
        self,
        user_id: str,
        org_id: str,
        provider: str,
        event: str,
        success: bool,
        request_id: str
    ) -> None:
        """Log OAuth authentication events"""
        self.logger.info(
            "oauth_event",
            user_id=user_id,
            org_id=org_id,
            provider=provider,
            event=event,
            success=success,
            request_id=request_id
        )
    
    def log_data_deletion(
        self,
        user_id: str,
        org_id: str,
        resource_type: str,
        resource_id: str,
        reason: str,
        request_id: str
    ) -> None:
        """Log data deletion for GDPR compliance"""
        self.logger.warning(
            "data_deletion",
            user_id=user_id,
            org_id=org_id,
            resource_type=resource_type,
            resource_id=resource_id,
            reason=reason,
            request_id=request_id
        )
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: Dict[str, Any],
        request_id: str
    ) -> None:
        """Log security events (failed logins, rate limits, etc.)"""
        log_method = getattr(self.logger, severity.lower(), self.logger.warning)
        log_method(
            "security_event",
            event_type=event_type,
            **details,
            request_id=request_id
        )


class PerformanceLogger:
    """
    Track performance metrics for monitoring and optimization.
    """
    
    def __init__(self):
        self.logger = structlog.get_logger("performance")
    
    def log_vector_query(
        self,
        namespace: str,
        query_vector_dim: int,
        top_k: int,
        filter_count: int,
        duration_ms: float,
        result_count: int
    ) -> None:
        """Log vector database query performance"""
        self.logger.info(
            "vector_query",
            namespace=namespace,
            query_vector_dim=query_vector_dim,
            top_k=top_k,
            filter_count=filter_count,
            duration_ms=duration_ms,
            result_count=result_count
        )
    
    def log_embedding_generation(
        self,
        text_length: int,
        batch_size: int,
        duration_ms: float,
        model: str
    ) -> None:
        """Log embedding generation performance"""
        self.logger.info(
            "embedding_generation",
            text_length=text_length,
            batch_size=batch_size,
            duration_ms=duration_ms,
            model=model
        )
    
    def log_agent_execution(
        self,
        agent_name: str,
        task_name: str,
        duration_ms: float,
        success: bool,
        token_count: int
    ) -> None:
        """Log CrewAI agent execution performance"""
        self.logger.info(
            "agent_execution",
            agent_name=agent_name,
            task_name=task_name,
            duration_ms=duration_ms,
            success=success,
            token_count=token_count
        )


# Initialize loggers
audit_logger = AuditLogger()
performance_logger = PerformanceLogger()

# Export setup function
__all__ = ["setup_logging", "audit_logger", "performance_logger"]
