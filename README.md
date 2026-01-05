# InboxMind - Enterprise Agentic RAG Platform

Production-ready, multi-tenant email intelligence platform using CrewAI, Pinecone, and FastAPI.

## Architecture

- **Backend**: FastAPI (async-first)
- **Vector Database**: Pinecone (cosine similarity, 1536 dimensions)
- **Agent Framework**: CrewAI (5-agent sequential pipeline)
- **Background Jobs**: APScheduler + Celery
- **Database**: PostgreSQL (SQLite for local dev)
- **OAuth**: Google & Microsoft OAuth 2.0
- **Security**: Fernet token encryption, tenant isolation

## Core Features

### RAG Pipeline
1. **RetrieverAgent** - Query Pinecone with metadata filters
2. **ContextAgent** - Reconstruct email threads chronologically
3. **AnalystAgent** - Multi-step reasoning and summarization
4. **ComplianceAgent** - PII redaction and content flagging
5. **AnswerAgent** - Grounded response generation with citations

### Multi-Tenancy
- Isolated by `org_id` + `user_id`
- Pinecone namespaces: `org_{org_id}_user_{user_id}`
- DB-level tenant filtering
- Encrypted OAuth tokens per user

### Email Ingestion
- OAuth-authenticated IMAP access (Gmail/Outlook)
- Continuous background sync
- Automatic embedding generation
- Metadata extraction (sender, thread, timestamp)

## Setup

### Prerequisites
```bash
Python 3.11+
PostgreSQL 14+
Redis 7+
Pinecone account
OpenAI API key
```

### Installation

```bash
# Clone repository
git clone <repo-url>
cd InboxMind

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Initialize database
alembic upgrade head

# Run application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Setup

```bash
docker-compose up -d
```

## API Endpoints

### OAuth
- `GET /api/v1/oauth/google` - Initiate Google OAuth
- `GET /api/v1/oauth/google/callback` - OAuth callback
- `GET /api/v1/oauth/microsoft` - Initiate Microsoft OAuth
- `GET /api/v1/oauth/microsoft/callback` - OAuth callback

### Emails
- `POST /api/v1/emails/sync` - Trigger manual sync
- `GET /api/v1/emails` - List user emails
- `GET /api/v1/emails/{email_id}` - Get email details

### RAG Query
```http
POST /api/v1/rag/query
Content-Type: application/json

{
  "query": "What decisions were made about the Q4 budget?",
  "filters": {
    "date_from": "2024-10-01",
    "date_to": "2024-12-31",
    "sender": "finance@company.com"
  }
}
```

Response:
```json
{
  "answer": "Based on the retrieved emails, three key decisions were made...",
  "sources": [
    {
      "email_id": "abc123",
      "subject": "Q4 Budget Approval",
      "sender": "cfo@company.com",
      "date": "2024-11-15T10:30:00Z",
      "relevance_score": 0.92
    }
  ],
  "metadata": {
    "retrieval_count": 15,
    "context_tokens": 2847,
    "processing_time_ms": 1253
  }
}
```

## Project Structure

```
app/
├── api/              # API routes
├── core/             # Config, security, logging
├── ingestion/        # Email fetching and parsing
├── embeddings/       # Embedding generation
├── vectorstore/      # Pinecone operations
├── crew/             # CrewAI agents and tasks
├── services/         # Business logic
├── models/           # SQLAlchemy models
└── db/               # Database session management

workers/              # Background job workers
scripts/              # Maintenance scripts
docker/               # Docker configuration
```

## Development

### Run Tests
```bash
pytest
pytest --cov=app tests/
```

### Code Quality
```bash
black .
ruff check .
mypy app/
```

### Background Workers
```bash
# Email ingestion worker
python workers/email_ingest_worker.py

# Embedding generation worker
python workers/embedding_worker.py
```

## Security

- OAuth tokens encrypted at rest with Fernet
- No tokens in logs or error messages
- Tenant isolation enforced at all layers
- PII redaction via ComplianceAgent
- Rate limiting on all endpoints
- Audit logging for all RAG queries

## Scaling Considerations

- Async I/O throughout
- Connection pooling (DB + Redis)
- Batch embedding generation
- Pinecone namespace-based sharding
- Horizontal worker scaling
- Configurable rate limits

## Compliance

- GDPR: User data deletion support
- SOC 2: Audit logging and encryption
- HIPAA: PII detection and redaction
- Data retention policies configurable

## Monitoring

- Structured logging (JSON)
- Request/response tracing
- Vector query performance metrics
- Agent execution tracking
- Error alerting

## License

Proprietary - Enterprise License

## Support

For issues or questions: support@inboxmind.ai
