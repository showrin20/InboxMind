# InboxMind - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Prerequisites
- Python 3.11+
- OpenAI API key
- Pinecone account (free tier works)

### 1. Clone and Setup

```bash
cd d:\InboxMind

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
copy .env.example .env

# Edit .env and set these REQUIRED values:
```

**Minimum Required Configuration:**

```env
# Generate secret key (run in Python):
# python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=your-generated-secret-key-here

# Pinecone (get from https://app.pinecone.io/)
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=email-rag-prod

# OpenAI (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=your-openai-api-key

# Fernet key for token encryption (run in Python):
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=your-generated-fernet-key

# Database (SQLite for local dev)
DATABASE_URL=sqlite+aiosqlite:///./inboxmind.db

# OAuth (set these later when implementing OAuth flow)
GOOGLE_CLIENT_ID=placeholder
GOOGLE_CLIENT_SECRET=placeholder
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/oauth/google/callback

MICROSOFT_CLIENT_ID=placeholder
MICROSOFT_CLIENT_SECRET=placeholder
MICROSOFT_REDIRECT_URI=http://localhost:8000/api/v1/oauth/microsoft/callback
```

### 3. Generate Keys

```python
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. Run the Application

```bash
# Start FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

### 5. Test the API

**Check Health:**
```bash
curl http://localhost:8000/health
```

**API Documentation:**
Open browser to: `http://localhost:8000/docs`

**Test RAG Query (once you have emails indexed):**
```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest project updates?",
    "filters": {
      "date_from": "2024-01-01",
      "date_to": "2024-12-31"
    }
  }'
```

## 📊 System Architecture

### Core Components Implemented

✅ **Configuration Management** (`app/core/config.py`)
- Pydantic settings with environment validation
- Multi-tenant configuration
- Production-ready defaults

✅ **Security Layer** (`app/core/security.py`)
- Fernet encryption for OAuth tokens
- JWT token management
- Tenant isolation validation

✅ **Structured Logging** (`app/core/logging.py`)
- JSON-formatted logs
- Audit trail for compliance
- Performance metrics

✅ **Database Models** (`app/models/`)
- User with encrypted OAuth tokens
- Email metadata and content
- Vector record tracking
- RAG query audit log
- Comprehensive audit log

✅ **Vector Store** (`app/vectorstore/`)
- Pinecone client with safe initialization
- Namespace-based tenant isolation
- Metadata filtering (date, sender, thread)

✅ **Embeddings Service** (`app/embeddings/`)
- OpenAI text-embedding-3-small (1536 dim)
- Text chunking with overlap
- Batch processing

✅ **CrewAI Agents** (`app/crew/agents/`)
1. **RetrieverAgent** - Queries Pinecone
2. **ContextAgent** - Reconstructs email threads
3. **AnalystAgent** - Extracts insights
4. **ComplianceAgent** - PII redaction
5. **AnswerAgent** - Generates cited responses

✅ **RAG Service** (`app/services/rag_service.py`)
- End-to-end query orchestration
- CrewAI pipeline execution
- Response formatting

✅ **FastAPI Application** (`app/main.py`)
- Health checks
- Request ID tracking
- Error handling
- CORS support

✅ **API Endpoints** (`app/api/routes/`)
- POST `/api/v1/rag/query` - RAG query endpoint
- GET `/health` - System health check

## 🔧 What's Next

### To Make This Production-Ready:

1. **Implement OAuth Flow** (`app/api/routes/oauth.py`)
   - Google OAuth 2.0 for Gmail
   - Microsoft OAuth for Outlook
   - Token refresh logic

2. **Implement Email Ingestion** (`app/ingestion/`)
   - IMAP fetcher for Gmail/Outlook
   - Email parser and normalizer
   - Metadata extraction

3. **Implement Background Workers** (`workers/`)
   - Email sync worker
   - Embedding generation worker
   - Scheduled jobs with APScheduler

4. **Add Authentication Middleware**
   - JWT token validation
   - Extract user_id and org_id from tokens
   - Protect all endpoints

5. **Add Email Management Endpoints**
   - List emails
   - Trigger manual sync
   - Delete user data (GDPR)

6. **Implement Admin Endpoints**
   - User management
   - System stats
   - Audit log access

7. **Add Tests** (`app/tests/`)
   - Unit tests for all services
   - Integration tests for RAG pipeline
   - E2E tests for API

8. **Production Deployment**
   - Set up PostgreSQL
   - Configure Redis for Celery
   - Set up monitoring (Prometheus, Grafana)
   - Configure logging aggregation (ELK, Datadog)

## 🐳 Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## 🔐 Security Checklist

- ✅ OAuth tokens encrypted at rest (Fernet)
- ✅ Tenant isolation enforced (namespace + metadata filters)
- ✅ No tokens in logs (sanitization)
- ✅ JWT for API authentication (ready to implement)
- ✅ Audit logging for all queries
- ✅ PII redaction in responses
- ✅ Input validation (Pydantic)
- ✅ CORS configured
- ✅ Error messages sanitized

## 📈 Monitoring

**Logs to Watch:**
- `app.services.rag_service` - RAG query execution
- `app.vectorstore.pinecone_index` - Vector operations
- `app.crew.crew_runner` - Agent execution
- `audit` - Compliance events
- `performance` - Performance metrics

**Metrics to Track:**
- RAG query latency
- Vector retrieval time
- Agent execution time
- Error rates
- Token usage

## 🧪 Testing RAG Pipeline

Once you have emails indexed in Pinecone, test with:

```python
import asyncio
from app.services.rag_service import get_rag_service

async def test_rag():
    rag_service = get_rag_service()
    
    result = await rag_service.query(
        query="What were the action items from last week's meeting?",
        org_id="org_demo",
        user_id="user_demo",
        date_from="2024-01-01",
        date_to="2024-12-31"
    )
    
    print("Answer:", result["answer"])
    print("Sources:", result["sources"])

asyncio.run(test_rag())
```

## 📚 Key Design Principles

1. **Fail Closed** - Better to refuse than hallucinate
2. **Always Grounded** - Every answer cites source emails
3. **Tenant Isolated** - Users can only access their data
4. **Audit Everything** - All queries logged for compliance
5. **Sequential Pipeline** - No agent may skip steps
6. **Production Ready** - No "demo" code, all enterprise-grade

## 🆘 Troubleshooting

**Pinecone Connection Error:**
- Verify `PINECONE_API_KEY` is correct
- Check Pinecone dashboard for index status
- Ensure index name matches `PINECONE_INDEX_NAME`

**Database Error:**
- For SQLite: ensure directory is writable
- For PostgreSQL: verify connection string
- Check database is initialized: logs show "Database initialized"

**Import Errors:**
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (need 3.11+)

**CrewAI Errors:**
- Verify `OPENAI_API_KEY` is set
- Check OpenAI API quota/billing
- Review CrewAI logs for agent failures

## 📧 Support

For issues or questions about the implementation, review:
- Code comments (extensive documentation)
- This QUICKSTART.md
- Main README.md

---

**Status:** Core RAG infrastructure complete ✅  
**Next:** Implement OAuth + Email Ingestion  
**Timeline:** Production-ready in ~2-3 weeks with OAuth and workers
