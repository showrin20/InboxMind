"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-01-08

Creates all initial tables for InboxMind:
- users: User accounts and OAuth configuration
- emails: Email metadata and content storage
- audit_logs: Comprehensive audit trail for compliance
- rag_queries: RAG query audit log
- vector_records: Tracking table for vector embeddings
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID primary key'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True, comment='User email address (unique)'),
        sa.Column('org_id', sa.String(50), nullable=False, index=True, comment='Organization ID for multi-tenancy'),
        sa.Column('hashed_password', sa.String(255), nullable=True, comment='Hashed password (may be null for OAuth-only users)'),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False, comment='Account active status'),
        sa.Column('is_superuser', sa.Boolean(), default=False, nullable=False, comment='Admin privileges'),
        sa.Column('full_name', sa.String(255), nullable=True, comment="User's full name"),
        sa.Column('oauth_provider', sa.String(50), nullable=True, comment="OAuth provider: 'google'"),
        sa.Column('oauth_provider_id', sa.String(255), nullable=True, index=True, comment='Unique ID from OAuth provider'),
        sa.Column('encrypted_access_token', sa.Text(), nullable=True, comment='Encrypted OAuth access token'),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True, comment='Encrypted OAuth refresh token'),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True, comment='OAuth token expiry'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='Last successful login'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True, comment='Last email sync time'),
    )

    # Create emails table
    op.create_table(
        'emails',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID primary key'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('org_id', sa.String(50), nullable=False, index=True, comment='Organization ID for tenant isolation'),
        sa.Column('user_id', sa.String(50), nullable=False, index=True, comment='User ID within the organization'),
        sa.Column('message_id', sa.String(255), nullable=False, index=True, comment='Email Message-ID header (unique per provider)'),
        sa.Column('thread_id', sa.String(255), nullable=True, index=True, comment='Email thread/conversation ID'),
        sa.Column('subject', sa.Text(), nullable=True, comment='Email subject line'),
        sa.Column('sender', sa.String(255), nullable=False, index=True, comment='From email address'),
        sa.Column('sender_name', sa.String(255), nullable=True, comment="Sender's display name"),
        sa.Column('recipients_to', sa.Text(), nullable=True, comment='To recipients (comma-separated)'),
        sa.Column('recipients_cc', sa.Text(), nullable=True, comment='CC recipients (comma-separated)'),
        sa.Column('recipients_bcc', sa.Text(), nullable=True, comment='BCC recipients (comma-separated)'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False, index=True, comment='When email was sent (from Date header)'),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False, comment='When we ingested this email'),
        sa.Column('body_text', sa.Text(), nullable=True, comment='Plain text email body'),
        sa.Column('body_html', sa.Text(), nullable=True, comment='HTML email body'),
        sa.Column('has_attachments', sa.Boolean(), default=False, nullable=False, comment='Whether email has attachments'),
        sa.Column('attachment_names', sa.Text(), nullable=True, comment='Attachment filenames (JSON array)'),
        sa.Column('labels', sa.Text(), nullable=True, comment='Email labels/folders (JSON array)'),
        sa.Column('is_read', sa.Boolean(), default=False, nullable=False, comment='Read status'),
        sa.Column('is_starred', sa.Boolean(), default=False, nullable=False, comment='Starred status'),
        sa.Column('is_archived', sa.Boolean(), default=False, nullable=False, comment='Archived status'),
        sa.Column('is_deleted', sa.Boolean(), default=False, nullable=False, comment='Soft delete flag'),
        sa.Column('importance', sa.String(20), nullable=True, comment='Email importance/priority'),
        sa.Column('raw_headers', sa.Text(), nullable=True, comment='Raw email headers (JSON)'),
    )
    
    # Create index for emails tenant isolation
    op.create_index('ix_emails_org_user', 'emails', ['org_id', 'user_id'])
    op.create_index('ix_emails_org_user_sent', 'emails', ['org_id', 'user_id', 'sent_at'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID primary key'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('event_type', sa.String(100), nullable=False, index=True, comment='Event type: oauth_event, rag_query, email_access, data_deletion, security_event'),
        sa.Column('event_category', sa.String(50), nullable=False, index=True, comment='Category: authentication, data_access, modification, deletion, security'),
        sa.Column('severity', sa.String(20), nullable=False, comment='Severity: info, warning, error, critical'),
        sa.Column('user_id', sa.String(50), nullable=True, index=True, comment='User who performed the action'),
        sa.Column('org_id', sa.String(50), nullable=True, index=True, comment='Organization context'),
        sa.Column('action', sa.String(255), nullable=False, comment='Specific action performed'),
        sa.Column('resource_type', sa.String(100), nullable=True, comment='Type of resource accessed'),
        sa.Column('resource_id', sa.String(255), nullable=True, comment='ID of resource accessed'),
        sa.Column('details', sa.Text(), nullable=True, comment='Additional details (JSON)'),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='Client IP address'),
        sa.Column('user_agent', sa.String(500), nullable=True, comment='Client user agent'),
        sa.Column('request_id', sa.String(36), nullable=True, comment='Request correlation ID'),
        sa.Column('success', sa.Boolean(), default=True, nullable=False, comment='Whether action succeeded'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if failed'),
    )
    
    # Create index for audit log queries
    op.create_index('ix_audit_logs_org_created', 'audit_logs', ['org_id', 'created_at'])
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])

    # Create rag_queries table
    op.create_table(
        'rag_queries',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID primary key'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('org_id', sa.String(50), nullable=False, index=True, comment='Organization ID for tenant isolation'),
        sa.Column('user_id', sa.String(50), nullable=False, index=True, comment='User ID within the organization'),
        sa.Column('query_text', sa.Text(), nullable=False, comment="User's query text"),
        sa.Column('filter_date_from', sa.DateTime(timezone=True), nullable=True, comment='Date filter: from'),
        sa.Column('filter_date_to', sa.DateTime(timezone=True), nullable=True, comment='Date filter: to'),
        sa.Column('filter_sender', sa.String(255), nullable=True, comment='Sender filter'),
        sa.Column('filter_keywords', sa.Text(), nullable=True, comment='Additional keyword filters (JSON array)'),
        sa.Column('answer_text', sa.Text(), nullable=False, comment='Generated answer from AnswerAgent'),
        sa.Column('sources_json', sa.Text(), nullable=True, comment='Source citations (JSON array of email metadata)'),
        sa.Column('retrieval_count', sa.Integer(), nullable=True, comment='Number of chunks retrieved'),
        sa.Column('relevance_scores', sa.Text(), nullable=True, comment='Relevance scores (JSON array)'),
        sa.Column('model_used', sa.String(100), nullable=True, comment='LLM model used for generation'),
        sa.Column('tokens_used', sa.Integer(), nullable=True, comment='Total tokens used'),
        sa.Column('latency_ms', sa.Integer(), nullable=True, comment='Query latency in milliseconds'),
        sa.Column('feedback_rating', sa.Integer(), nullable=True, comment='User feedback rating (1-5)'),
        sa.Column('feedback_text', sa.Text(), nullable=True, comment='User feedback text'),
    )
    
    # Create index for rag queries
    op.create_index('ix_rag_queries_org_user_created', 'rag_queries', ['org_id', 'user_id', 'created_at'])

    # Create vector_records table
    op.create_table(
        'vector_records',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID primary key'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('org_id', sa.String(50), nullable=False, index=True, comment='Organization ID for tenant isolation'),
        sa.Column('user_id', sa.String(50), nullable=False, index=True, comment='User ID within the organization'),
        sa.Column('vector_id', sa.String(255), nullable=False, unique=True, index=True, comment='Pinecone vector ID (UUID)'),
        sa.Column('namespace', sa.String(255), nullable=False, index=True, comment='Pinecone namespace (org_{org_id}_user_{user_id})'),
        sa.Column('email_id', sa.String(36), sa.ForeignKey('emails.id', ondelete='CASCADE'), nullable=False, index=True, comment='Source email ID'),
        sa.Column('chunk_index', sa.Integer(), nullable=False, comment='Chunk number for this email (0-indexed)'),
        sa.Column('chunk_text', sa.Text(), nullable=False, comment='Text content of this chunk'),
        sa.Column('chunk_token_count', sa.Integer(), nullable=True, comment='Token count of chunk'),
        sa.Column('embedding_model', sa.String(100), nullable=True, comment='Model used for embedding'),
        sa.Column('metadata_json', sa.Text(), nullable=True, comment='Additional metadata stored in Pinecone (JSON)'),
    )
    
    # Create index for vector records
    op.create_index('ix_vector_records_org_user', 'vector_records', ['org_id', 'user_id'])
    op.create_index('ix_vector_records_email_chunk', 'vector_records', ['email_id', 'chunk_index'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('vector_records')
    op.drop_table('rag_queries')
    op.drop_table('audit_logs')
    op.drop_table('emails')
    op.drop_table('users')
