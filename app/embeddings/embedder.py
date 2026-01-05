"""
Embedding Generation Service
OpenAI embeddings with chunking and batch processing
"""
from typing import List, Dict, Any, Tuple
import logging
from datetime import datetime
import tiktoken
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import performance_logger
from app.embeddings.schema import EmbeddingChunk, EmailEmbedding, VectorUpsertRecord

settings = get_settings()
logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings using OpenAI.
    Handles text chunking, batch processing, and error recovery.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimension = settings.PINECONE_DIMENSION
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        
        # Chunking configuration
        self.max_tokens_per_chunk = 512
        self.chunk_overlap = 50
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed, estimating: {e}")
            return len(text) // 4
    
    def chunk_text(self, text: str) -> List[EmbeddingChunk]:
        """
        Split text into overlapping chunks for embedding.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of EmbeddingChunk objects
        """
        if not text or not text.strip():
            return []
        
        # Simple sentence-based chunking
        sentences = text.replace('\n', ' ').split('. ')
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_tokens = self.count_tokens(sentence)
            
            if current_tokens + sentence_tokens > self.max_tokens_per_chunk:
                # Save current chunk
                if current_chunk:
                    chunk_text = '. '.join(current_chunk) + '.'
                    chunks.append(
                        EmbeddingChunk(
                            chunk_text=chunk_text,
                            chunk_index=chunk_index,
                            token_count=self.count_tokens(chunk_text)
                        )
                    )
                    chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and len(current_chunk) > 1:
                    current_chunk = current_chunk[-1:]
                    current_tokens = self.count_tokens(current_chunk[0])
                else:
                    current_chunk = []
                    current_tokens = 0
            
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = '. '.join(current_chunk) + '.'
            chunks.append(
                EmbeddingChunk(
                    chunk_text=chunk_text,
                    chunk_index=chunk_index,
                    token_count=self.count_tokens(chunk_text)
                )
            )
        
        logger.debug(f"Chunked text into {len(chunks)} chunks")
        return chunks
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (1536 dimensions)
        """
        if not text or not text.strip():
            logger.warning("Attempted to embed empty text")
            return [0.0] * self.dimension
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            
            # Verify dimension
            if len(embedding) != self.dimension:
                logger.error(f"Unexpected embedding dimension: {len(embedding)}")
                raise ValueError(f"Expected {self.dimension} dimensions, got {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {type(e).__name__}: {e}")
            raise
    
    async def generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        start_time = datetime.now()
        
        try:
            # OpenAI supports batch embeddings
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                encoding_format="float"
            )
            
            embeddings = [item.embedding for item in response.data]
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log performance
            total_text_length = sum(len(t) for t in texts)
            performance_logger.log_embedding_generation(
                text_length=total_text_length,
                batch_size=len(texts),
                duration_ms=duration_ms,
                model=self.model
            )
            
            logger.info(
                f"Generated {len(embeddings)} embeddings in {duration_ms:.2f}ms "
                f"(avg {duration_ms/len(embeddings):.2f}ms per embedding)"
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise
    
    async def embed_email(
        self,
        email_id: str,
        email_content: str,
        metadata: Dict[str, Any]
    ) -> Tuple[EmailEmbedding, List[VectorUpsertRecord]]:
        """
        Generate embeddings for an email with chunking.
        
        Args:
            email_id: Email ID
            email_content: Email text content
            metadata: Email metadata for vector storage
            
        Returns:
            Tuple of (EmailEmbedding, List[VectorUpsertRecord])
        """
        start_time = datetime.now()
        
        # Chunk the email
        chunks = self.chunk_text(email_content)
        
        if not chunks:
            logger.warning(f"No chunks generated for email {email_id}")
            return (
                EmailEmbedding(
                    email_id=email_id,
                    chunks=[],
                    embedding_model=self.model,
                    dimension=self.dimension,
                    total_tokens=0
                ),
                []
            )
        
        # Generate embeddings for all chunks
        chunk_texts = [chunk.chunk_text for chunk in chunks]
        embeddings = await self.generate_embeddings_batch(chunk_texts)
        
        # Create vector upsert records
        upsert_records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = f"{email_id}_chunk_{i}"
            
            # Add chunk-specific metadata
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                "chunk_index": i,
                "chunk_token_count": chunk.token_count,
                "text_preview": chunk.chunk_text[:200]
            })
            
            upsert_records.append(
                VectorUpsertRecord(
                    vector_id=vector_id,
                    embedding=embedding,
                    metadata=chunk_metadata
                )
            )
        
        total_tokens = sum(chunk.token_count for chunk in chunks)
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"Embedded email {email_id}: {len(chunks)} chunks, "
            f"{total_tokens} tokens in {duration_ms:.2f}ms"
        )
        
        email_embedding = EmailEmbedding(
            email_id=email_id,
            chunks=chunks,
            embedding_model=self.model,
            dimension=self.dimension,
            total_tokens=total_tokens
        )
        
        return email_embedding, upsert_records
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a RAG query.
        
        Args:
            query: User query text
            
        Returns:
            Query embedding vector
        """
        logger.info(f"Generating query embedding for: {query[:100]}...")
        return await self.generate_embedding(query)


# Singleton instance
_embedding_service: EmbeddingService = None


def get_embedding_service() -> EmbeddingService:
    """Get or create EmbeddingService singleton"""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    
    return _embedding_service


# Export
__all__ = ["EmbeddingService", "get_embedding_service", "EmbeddingChunk", "EmailEmbedding"]
