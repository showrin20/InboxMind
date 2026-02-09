"""
Chat Service - Handles Email Vectorization and Chat Queries
Provides conversational interface over vectorized emails with special command handling
"""
from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime, timezone
import uuid
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

from app.embeddings.embedder import get_embedding_service
from app.vectorstore.pinecone_index import get_pinecone_operations
from app.vectorstore.filters import create_rag_query_filter
from app.models.email import Email
from app.core.config import get_settings
from app.core.logging import audit_logger
import google.generativeai as genai

settings = get_settings()
logger = logging.getLogger(__name__)


class ChatService:
    """
    High-level chat service that provides:
    1. Email vectorization (storing body_text in Pinecone)
    2. Natural language query answering via vector search
    3. Special command handling (e.g., "summarize last 3 mails")
    """
    
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.pinecone_ops = get_pinecone_operations()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    # =========================================================================
    # VECTORIZATION METHODS
    # =========================================================================
    
    async def vectorize_emails(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        batch_size: int = 50,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Vectorize all email body_text for a user and store in Pinecone.
        
        Args:
            db: Database session
            org_id: Organization ID
            user_id: User ID
            batch_size: Number of emails to process per batch
            force_reindex: If True, re-vectorize already embedded emails
            
        Returns:
            Dictionary with vectorization stats
        """
        start_time = datetime.now()
        
        # Get emails to vectorize
        if force_reindex:
            query = select(Email).where(
                and_(
                    Email.org_id == org_id,
                    Email.user_id == user_id
                )
            ).order_by(desc(Email.sent_at))
        else:
            query = select(Email).where(
                and_(
                    Email.org_id == org_id,
                    Email.user_id == user_id,
                    Email.is_embedded == False
                )
            ).order_by(desc(Email.sent_at))
        
        result = await db.execute(query)
        emails = result.scalars().all()
        
        if not emails:
            return {
                "status": "success",
                "message": "No emails to vectorize",
                "vectorized_count": 0,
                "total_chunks": 0,
                "processing_time_ms": 0
            }
        
        logger.info(f"Starting vectorization of {len(emails)} emails for user {user_id}")
        
        namespace = settings.get_namespace(org_id, user_id)
        total_chunks = 0
        vectorized_count = 0
        errors = []
        
        # Process in batches
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            
            for email in batch:
                try:
                    # Skip emails without body text
                    if not email.body_text or not email.body_text.strip():
                        logger.debug(f"Skipping email {email.id} - no body text")
                        continue
                    
                    # Get metadata for vector storage
                    metadata = email.to_metadata_dict()
                    
                    # Generate embeddings
                    email_embedding, upsert_records = await self.embedding_service.embed_email(
                        email_id=str(email.id),
                        email_content=email.body_text,
                        metadata=metadata
                    )
                    
                    if upsert_records:
                        # Convert to Pinecone format
                        vectors = [
                            (record.vector_id, record.embedding, record.metadata)
                            for record in upsert_records
                        ]
                        
                        # Upsert to Pinecone
                        success = self.pinecone_ops.upsert_vectors(
                            vectors=vectors,
                            namespace=namespace
                        )
                        
                        if success:
                            # Mark email as embedded
                            email.is_embedded = True
                            email.embedding_generated_at = datetime.now(timezone.utc)
                            db.add(email)
                            
                            total_chunks += len(upsert_records)
                            vectorized_count += 1
                        else:
                            errors.append(f"Email {email.id}: Pinecone upsert failed")
                            
                except Exception as e:
                    error_msg = f"Email {email.id}: {type(e).__name__}: {e}"
                    logger.error(f"Vectorization error: {error_msg}")
                    errors.append(error_msg)
            
            # Commit batch
            await db.commit()
            logger.info(f"Vectorized batch {i//batch_size + 1}: {vectorized_count} emails, {total_chunks} chunks")
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "status": "success" if not errors else "partial",
            "message": f"Vectorized {vectorized_count} emails into {total_chunks} chunks",
            "vectorized_count": vectorized_count,
            "total_chunks": total_chunks,
            "processing_time_ms": processing_time,
            "errors": errors if errors else None
        }
    
    async def get_vectorization_status(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get current vectorization status for a user.
        """
        # Count total emails
        total_query = select(func.count(Email.id)).where(
            and_(
                Email.org_id == org_id,
                Email.user_id == user_id
            )
        )
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0
        
        # Count embedded emails
        embedded_query = select(func.count(Email.id)).where(
            and_(
                Email.org_id == org_id,
                Email.user_id == user_id,
                Email.is_embedded == True
            )
        )
        embedded_result = await db.execute(embedded_query)
        embedded_count = embedded_result.scalar() or 0
        
        # Get Pinecone stats
        namespace = settings.get_namespace(org_id, user_id)
        try:
            index = self.pinecone_ops.index
            stats = index.describe_index_stats()
            namespace_stats = stats.namespaces.get(namespace, {})
            vector_count = getattr(namespace_stats, 'vector_count', 0) if namespace_stats else 0
        except Exception as e:
            logger.warning(f"Could not get Pinecone stats: {e}")
            vector_count = 0
        
        return {
            "total_emails": total_count,
            "embedded_emails": embedded_count,
            "pending_emails": total_count - embedded_count,
            "vector_count": vector_count,
            "is_ready": embedded_count > 0,
            "completion_percentage": round((embedded_count / total_count * 100), 2) if total_count > 0 else 0
        }
    
    # =========================================================================
    # CHAT METHODS
    # =========================================================================
    
    async def chat(
        self,
        db: AsyncSession,
        query: str,
        org_id: str,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a chat query about emails.
        
        Handles:
        1. Special commands (e.g., "summarize last 3 mails")
        2. Vector search queries
        3. General questions about emails
        
        Args:
            db: Database session
            query: User's natural language query
            org_id: Organization ID
            user_id: User ID
            filters: Optional filters (date_from, date_to, sender)
            request_id: Request tracing ID
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        
        logger.info(f"Chat query: request_id={request_id}, query={query[:100]}")
        
        try:
            # Check for special commands
            special_result = await self._handle_special_commands(
                db=db,
                query=query,
                org_id=org_id,
                user_id=user_id,
                request_id=request_id
            )
            
            if special_result:
                return special_result
            
            # Regular vector search query
            return await self._vector_search_query(
                db=db,
                query=query,
                org_id=org_id,
                user_id=user_id,
                filters=filters,
                request_id=request_id,
                start_time=start_time
            )
            
        except Exception as e:
            logger.error(f"Chat query failed: {e}", exc_info=True)
            return {
                "answer": "I encountered an error processing your query. Please try again.",
                "sources": [],
                "metadata": {
                    "request_id": request_id,
                    "error": True,
                    "error_message": str(e)
                }
            }
    
    async def _handle_special_commands(
        self,
        db: AsyncSession,
        query: str,
        org_id: str,
        user_id: str,
        request_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Handle special command queries like "summarize last 3 mails".
        
        Supported patterns:
        - "summarize last N mails/emails"
        - "show last N emails"
        - "what are my recent N mails"
        - "latest N emails summary"
        """
        query_lower = query.lower().strip()
        
        # Pattern matching for "last N mails" type queries
        patterns = [
            r"(?:summarize|summary|show|get|list|what are|display)?\s*(?:my|the)?\s*(?:last|recent|latest)\s+(\d+)\s*(?:mail|email|message)s?",
            r"(?:last|recent|latest)\s+(\d+)\s*(?:mail|email|message)s?\s*(?:summary|summarize)?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                count = int(match.group(1))
                # Limit to reasonable number
                count = min(count, 20)
                
                return await self._summarize_last_n_emails(
                    db=db,
                    org_id=org_id,
                    user_id=user_id,
                    count=count,
                    request_id=request_id
                )
        
        # Check for "unread" queries
        if "unread" in query_lower:
            return await self._handle_unread_query(
                db=db,
                org_id=org_id,
                user_id=user_id,
                query=query,
                request_id=request_id
            )
        
        return None
    
    async def _summarize_last_n_emails(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        count: int,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Summarize the last N emails for a user.
        """
        start_time = datetime.now()
        
        # Fetch last N emails
        query = select(Email).where(
            and_(
                Email.org_id == org_id,
                Email.user_id == user_id
            )
        ).order_by(desc(Email.sent_at)).limit(count)
        
        result = await db.execute(query)
        emails = result.scalars().all()
        
        if not emails:
            return {
                "answer": f"You don't have any emails to summarize. Please sync your emails first.",
                "sources": [],
                "metadata": {
                    "request_id": request_id,
                    "command": "summarize_last_n",
                    "count": count,
                    "found": 0
                }
            }
        
        # Build context for summarization
        email_summaries = []
        sources = []
        
        for i, email in enumerate(emails, 1):
            email_text = f"""
Email {i}:
- From: {email.sender} ({email.sender_name or 'N/A'})
- Subject: {email.subject or '(No Subject)'}
- Date: {email.sent_at.strftime('%Y-%m-%d %H:%M') if email.sent_at else 'Unknown'}
- Content: {(email.body_text or '')[:500]}{'...' if email.body_text and len(email.body_text) > 500 else ''}
"""
            email_summaries.append(email_text)
            
            sources.append({
                "email_id": str(email.id),
                "subject": email.subject,
                "sender": email.sender,
                "date": email.sent_at.isoformat() if email.sent_at else None
            })
        
        # Generate summary using Gemini
        prompt = f"""You are an email assistant. Summarize the following {len(emails)} emails concisely.
For each email, provide:
1. Key points or main message
2. Any action items or deadlines
3. Important decisions or information

Emails:
{''.join(email_summaries)}

Provide a clear, organized summary. Group similar topics if applicable."""
        
        try:
            response = self.model.generate_content(prompt)
            answer = response.text
        except Exception as e:
            logger.error(f"Gemini summarization failed: {e}")
            answer = f"Here are your last {len(emails)} emails:\n\n"
            for s in email_summaries:
                answer += s + "\n"
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "answer": answer,
            "sources": sources,
            "metadata": {
                "request_id": request_id,
                "command": "summarize_last_n",
                "count": count,
                "found": len(emails),
                "processing_time_ms": processing_time
            }
        }
    
    async def _handle_unread_query(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        query: str,
        request_id: str
    ) -> Dict[str, Any]:
        """Handle queries about unread emails."""
        
        # Count unread emails
        unread_query = select(func.count(Email.id)).where(
            and_(
                Email.org_id == org_id,
                Email.user_id == user_id,
                Email.is_read == False
            )
        )
        result = await db.execute(unread_query)
        unread_count = result.scalar() or 0
        
        if unread_count == 0:
            return {
                "answer": "You have no unread emails. Great job keeping your inbox clean! 🎉",
                "sources": [],
                "metadata": {
                    "request_id": request_id,
                    "command": "unread_count",
                    "unread_count": 0
                }
            }
        
        # Get unread emails summary
        emails_query = select(Email).where(
            and_(
                Email.org_id == org_id,
                Email.user_id == user_id,
                Email.is_read == False
            )
        ).order_by(desc(Email.sent_at)).limit(10)
        
        result = await db.execute(emails_query)
        emails = result.scalars().all()
        
        sources = []
        email_list = []
        for email in emails:
            sources.append({
                "email_id": str(email.id),
                "subject": email.subject,
                "sender": email.sender,
                "date": email.sent_at.isoformat() if email.sent_at else None
            })
            email_list.append(f"- **{email.subject or '(No Subject)'}** from {email.sender}")
        
        answer = f"You have **{unread_count} unread email(s)**.\n\n"
        if unread_count > 10:
            answer += f"Here are the most recent 10:\n\n"
        answer += "\n".join(email_list)
        
        return {
            "answer": answer,
            "sources": sources,
            "metadata": {
                "request_id": request_id,
                "command": "unread_emails",
                "unread_count": unread_count
            }
        }
    
    async def _vector_search_query(
        self,
        db: AsyncSession,
        query: str,
        org_id: str,
        user_id: str,
        filters: Optional[Dict[str, Any]],
        request_id: str,
        start_time: datetime
    ) -> Dict[str, Any]:
        """
        Execute a vector search query on emails.
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_query_embedding(query)
        
        # Build namespace for tenant isolation
        namespace = settings.get_namespace(org_id, user_id)
        
        # Build metadata filters
        filters = filters or {}
        filter_dict = create_rag_query_filter(
            org_id=org_id,
            user_id=user_id,
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
            sender=filters.get("sender")
        )
        
        # Query Pinecone
        retrieved_chunks = self.pinecone_ops.query_vectors(
            query_vector=query_embedding,
            namespace=namespace,
            top_k=settings.MAX_RETRIEVAL_RESULTS,
            filter_dict=filter_dict,
            include_metadata=True
        )
        
        if not retrieved_chunks:
            # Check if emails are vectorized
            status = await self.get_vectorization_status(db, org_id, user_id)
            
            if status["embedded_emails"] == 0:
                return {
                    "answer": (
                        "Your emails haven't been vectorized yet. "
                        "Please call POST /api/v1/chat/vectorize first to enable semantic search."
                    ),
                    "sources": [],
                    "metadata": {
                        "request_id": request_id,
                        "retrieval_count": 0,
                        "vectorization_status": status
                    }
                }
            
            return {
                "answer": (
                    "I couldn't find any emails matching your query. "
                    "Try rephrasing your question or broadening your search criteria."
                ),
                "sources": [],
                "metadata": {
                    "request_id": request_id,
                    "retrieval_count": 0
                }
            }
        
        # Build context from retrieved chunks
        context_parts = []
        sources = []
        seen_emails = set()
        
        for chunk in retrieved_chunks:
            metadata = chunk.get("metadata", {})
            email_id = metadata.get("email_id")
            
            chunk_context = f"""
[Email from {metadata.get('sender', 'Unknown')}]
Subject: {metadata.get('subject', 'No Subject')}
Date: {metadata.get('sent_at', 'Unknown')}
Content: {metadata.get('text_preview', '')}
---"""
            context_parts.append(chunk_context)
            
            # Add unique sources
            if email_id and email_id not in seen_emails:
                seen_emails.add(email_id)
                sources.append({
                    "email_id": email_id,
                    "subject": metadata.get("subject"),
                    "sender": metadata.get("sender"),
                    "date": metadata.get("sent_at"),
                    "relevance_score": chunk.get("score")
                })
        
        # Generate answer using Gemini
        context = "\n".join(context_parts)
        prompt = f"""You are an intelligent email assistant. Answer the user's question based ONLY on the provided email context.
If the context doesn't contain enough information to answer the question, say so.
Always cite which emails you're referencing.

User Question: {query}

Email Context:
{context}

Provide a clear, helpful answer:"""
        
        try:
            response = self.model.generate_content(prompt)
            answer = response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            answer = "I found relevant emails but encountered an error generating the answer. Please try again."
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "answer": answer,
            "sources": sources[:10],  # Limit sources
            "metadata": {
                "request_id": request_id,
                "retrieval_count": len(retrieved_chunks),
                "unique_emails": len(seen_emails),
                "processing_time_ms": processing_time
            }
        }


# Singleton
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create ChatService singleton"""
    global _chat_service
    
    if _chat_service is None:
        _chat_service = ChatService()
    
    return _chat_service


# Export
__all__ = ["ChatService", "get_chat_service"]
