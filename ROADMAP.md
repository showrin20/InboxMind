# 🗺️ Development Roadmap - Next Steps

## Phase 1: OAuth & Email Sync (Week 1-2)

### 1.1 Google OAuth Implementation
**File:** `app/api/routes/oauth.py`

```python
@router.get("/google")
async def google_oauth_init():
    """Initiate Google OAuth flow"""
    # Generate state token
    # Redirect to Google OAuth URL
    # Include Gmail scopes

@router.get("/google/callback")
async def google_oauth_callback(code: str, state: str):
    """Handle Google OAuth callback"""
    # Verify state token
    # Exchange code for tokens
    # Encrypt and store tokens
    # Create/update user record
```

**Resources:**
- https://developers.google.com/identity/protocols/oauth2
- `google-auth-oauthlib` library

---

### 1.2 Microsoft OAuth Implementation
**File:** `app/api/routes/oauth.py`

```python
@router.get("/microsoft")
async def microsoft_oauth_init():
    """Initiate Microsoft OAuth flow"""

@router.get("/microsoft/callback")
async def microsoft_oauth_callback(code: str, state: str):
    """Handle Microsoft OAuth callback"""
```

**Resources:**
- https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow
- `msal` library

---

### 1.3 Token Service
**File:** `app/services/token_service.py`

```python
class TokenService:
    async def store_oauth_tokens(user_id, provider, access_token, refresh_token):
        """Encrypt and store OAuth tokens"""
    
    async def refresh_oauth_token(user_id):
        """Refresh expired OAuth token"""
    
    async def get_valid_token(user_id):
        """Get valid token, refresh if needed"""
```

---

### 1.4 IMAP Email Fetcher
**File:** `app/ingestion/imap_fetcher.py`

```python
class IMAPFetcher:
    def __init__(self, provider: str):
        """Initialize IMAP connection for Gmail/Outlook"""
    
    async def connect(self, access_token: str):
        """Connect using OAuth2 XOAUTH2"""
    
    async def fetch_emails(self, since_date: datetime, limit: int = 100):
        """Fetch emails since date"""
    
    async def fetch_email_by_id(self, message_id: str):
        """Fetch specific email"""
```

**IMAP Servers:**
- Gmail: `imap.gmail.com:993`
- Outlook: `outlook.office365.com:993`

**Libraries:**
- `imaplib` (built-in)
- Or `aioimaplib` for async

---

### 1.5 Email Parser
**File:** `app/ingestion/email_parser.py`

```python
class EmailParser:
    def parse_email(self, raw_email: bytes):
        """Parse raw email into structured format"""
        # Extract headers
        # Parse body (text + HTML)
        # Extract attachments metadata
        # Extract thread ID
        # Return Email model
```

**Libraries:**
- `email` (built-in)
- `beautifulsoup4` for HTML cleaning

---

### 1.6 Email Service
**File:** `app/services/email_service.py`

```python
class EmailService:
    async def sync_user_emails(self, user_id: str):
        """Sync emails for a user"""
        # Get valid OAuth token
        # Connect to IMAP
        # Fetch new emails since last sync
        # Parse emails
        # Store in database
        # Queue for embedding
    
    async def get_user_emails(self, user_id: str, filters: dict):
        """List user's emails with filters"""
    
    async def delete_user_emails(self, user_id: str):
        """Delete all emails for user (GDPR)"""
```

---

## Phase 2: Background Workers (Week 3)

### 2.1 Email Ingestion Worker
**File:** `workers/email_ingest_worker.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def sync_all_users_emails():
    """Periodic job to sync emails for all users"""
    users = await get_active_users()
    for user in users:
        if user.email_sync_enabled:
            await email_service.sync_user_emails(user.id)

scheduler = AsyncIOScheduler()
scheduler.add_job(
    sync_all_users_emails,
    'interval',
    minutes=settings.EMAIL_SYNC_INTERVAL_MINUTES
)
scheduler.start()
```

---

### 2.2 Embedding Generation Worker
**File:** `workers/embedding_worker.py`

```python
async def generate_embeddings_batch():
    """Process unembedded emails"""
    # Fetch emails where is_embedded=False
    # Generate embeddings in batches
    # Upsert to Pinecone
    # Update email records
    # Create VectorRecord entries

scheduler.add_job(
    generate_embeddings_batch,
    'interval',
    minutes=5
)
```

---

### 2.3 Celery Setup (Alternative)
**File:** `workers/celery_app.py`

```python
from celery import Celery

app = Celery('inboxmind', broker=settings.REDIS_URL)

@app.task
def sync_user_emails_task(user_id: str):
    """Celery task for email sync"""
    asyncio.run(email_service.sync_user_emails(user_id))

@app.task
def generate_embeddings_task(email_ids: List[str]):
    """Celery task for embedding generation"""
```

---

## Phase 3: Email Management API (Week 3)

### 3.1 Email Endpoints
**File:** `app/api/routes/emails.py`

```python
@router.get("/")
async def list_emails(
    user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
    sender: str = None,
    date_from: str = None
):
    """List user's emails with pagination and filters"""

@router.get("/{email_id}")
async def get_email(email_id: str, user: User = Depends(get_current_user)):
    """Get specific email"""

@router.post("/sync")
async def trigger_sync(user: User = Depends(get_current_user)):
    """Manually trigger email sync"""

@router.delete("/{email_id}")
async def delete_email(email_id: str, user: User = Depends(get_current_user)):
    """Delete specific email"""
```

---

## Phase 4: Authentication Middleware (Week 4)

### 4.1 JWT Authentication
**File:** `app/api/deps.py`

```python
from fastapi import Depends, HTTPException, Header
from app.core.security import jwt_manager

async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """Extract and validate JWT token, return User"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    
    token = authorization.split(" ")[1]
    payload = jwt_manager.decode_access_token(token)
    
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    
    user = await db.get(User, payload["user_id"])
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    
    return user
```

---

### 4.2 Update RAG Endpoint
**File:** `app/api/routes/rag.py`

```python
@router.post("/query")
async def rag_query(
    request_body: RAGQueryRequest,
    user: User = Depends(get_current_user),  # Add authentication
    request: Request
):
    # Now use user.id and user.org_id instead of hardcoded values
    result = await rag_service.query(
        query=request_body.query,
        org_id=user.org_id,
        user_id=user.id,
        ...
    )
```

---

## Phase 5: Admin Endpoints (Week 4)

### 5.1 Admin Routes
**File:** `app/api/routes/admin.py`

```python
@router.get("/users")
async def list_users(admin: User = Depends(require_admin)):
    """List all users (admin only)"""

@router.get("/stats")
async def system_stats(admin: User = Depends(require_admin)):
    """System statistics"""
    return {
        "total_users": await db.count(User),
        "total_emails": await db.count(Email),
        "total_queries": await db.count(RAGQuery),
        "pinecone_stats": pinecone_client.get_index_stats()
    }

@router.get("/audit-logs")
async def get_audit_logs(admin: User = Depends(require_admin)):
    """Retrieve audit logs"""
```

---

## Phase 6: Testing (Week 5)

### 6.1 Unit Tests
**File:** `app/tests/test_vectorstore.py`

```python
import pytest
from app.vectorstore.pinecone_index import get_pinecone_operations

@pytest.mark.asyncio
async def test_vector_upsert():
    ops = get_pinecone_operations()
    vectors = [("test_id", [0.1] * 1536, {"test": "metadata"})]
    result = ops.upsert_vectors(vectors, "test_namespace")
    assert result == True

@pytest.mark.asyncio
async def test_vector_query():
    ops = get_pinecone_operations()
    query_vector = [0.1] * 1536
    results = ops.query_vectors(query_vector, "test_namespace", top_k=5)
    assert isinstance(results, list)
```

---

### 6.2 Integration Tests
**File:** `app/tests/test_rag_pipeline.py`

```python
@pytest.mark.asyncio
async def test_end_to_end_rag():
    """Test complete RAG pipeline"""
    # Create test user
    # Create test emails in DB
    # Generate embeddings
    # Upsert to Pinecone
    # Run RAG query
    # Verify response structure
```

---

### 6.3 API Tests
**File:** `app/tests/test_api.py`

```python
from fastapi.testclient import TestClient

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]

def test_rag_query_endpoint():
    response = client.post(
        "/api/v1/rag/query",
        json={"query": "test query"},
        headers={"Authorization": f"Bearer {test_token}"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()
```

---

## Phase 7: Monitoring & Deployment (Week 6)

### 7.1 Prometheus Metrics
**File:** `app/core/metrics.py`

```python
from prometheus_client import Counter, Histogram

rag_query_counter = Counter('rag_queries_total', 'Total RAG queries')
rag_query_duration = Histogram('rag_query_duration_seconds', 'RAG query duration')
```

---

### 7.2 Production Environment
**File:** `.env.production`

```bash
APP_ENV=production
DEBUG=False
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/inboxmind
REDIS_URL=redis://prod-redis:6379/0
LOG_LEVEL=INFO
```

---

### 7.3 Kubernetes Deployment
**File:** `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inboxmind-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: inboxmind-api
  template:
    metadata:
      labels:
        app: inboxmind-api
    spec:
      containers:
      - name: api
        image: inboxmind:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: inboxmind-secrets
              key: database-url
```

---

## Development Checklist

### OAuth & Email Sync
- [ ] Google OAuth flow
- [ ] Microsoft OAuth flow
- [ ] Token refresh logic
- [ ] IMAP connection
- [ ] Email parsing
- [ ] Email storage
- [ ] Manual sync endpoint

### Background Workers
- [ ] APScheduler setup
- [ ] Email sync worker
- [ ] Embedding generation worker
- [ ] Worker monitoring

### Authentication
- [ ] JWT middleware
- [ ] Token validation
- [ ] User extraction
- [ ] Protected endpoints

### Email Management
- [ ] List emails endpoint
- [ ] Get email endpoint
- [ ] Delete email endpoint
- [ ] Email filters

### Admin Features
- [ ] User management
- [ ] System statistics
- [ ] Audit log access
- [ ] Admin-only middleware

### Testing
- [ ] Unit tests (80%+ coverage)
- [ ] Integration tests
- [ ] API tests
- [ ] Load testing

### Monitoring
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] Error alerting
- [ ] Log aggregation

### Deployment
- [ ] Docker optimization
- [ ] Kubernetes manifests
- [ ] CI/CD pipeline
- [ ] Production environment

---

## Quick Wins (Can Do Now)

### 1. Add Request ID to Responses
```python
@app.middleware("http")
async def add_request_id_to_response(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response
```

### 2. Add Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/query")
@limiter.limit("100/minute")
async def rag_query(...):
    ...
```

### 3. Add Response Caching
```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def cached_rag_query(query: str, filters: str):
    """Cache frequent queries"""
```

### 4. Add Health Check Details
```python
@app.get("/health/detailed")
async def detailed_health():
    return {
        "database": await check_db_health(),
        "pinecone": pinecone_client.health_check(),
        "redis": await check_redis_health(),
        "workers": await check_workers_health()
    }
```

---

## Resources

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- CrewAI: https://docs.crewai.com/
- Pinecone: https://docs.pinecone.io/
- OpenAI: https://platform.openai.com/docs/

### Libraries to Add
```txt
# Rate limiting
slowapi==0.1.9

# Monitoring
prometheus-client==0.19.0

# Testing
pytest-asyncio==0.23.3
pytest-mock==3.12.0
httpx==0.26.0

# Worker scheduling
apscheduler==3.10.4
celery==5.3.6

# Email
aioimaplib==1.0.1
```

---

## Timeline Summary

| Phase | Duration | Status |
|-------|----------|--------|
| Core Infrastructure | Week -1 | ✅ Done |
| OAuth & Email Sync | Week 1-2 | 🔜 Next |
| Background Workers | Week 3 | 📅 Planned |
| Authentication & APIs | Week 4 | 📅 Planned |
| Testing | Week 5 | 📅 Planned |
| Monitoring & Deploy | Week 6 | 📅 Planned |

**Total to Production:** 6 weeks from now

---

## Success Criteria

### MVP (Week 2)
- [ ] Users can OAuth with Gmail/Outlook
- [ ] Emails automatically synced
- [ ] RAG queries work end-to-end
- [ ] Basic authentication

### Beta (Week 4)
- [ ] Full email management
- [ ] Admin dashboard
- [ ] Background workers running
- [ ] 80%+ test coverage

### Production (Week 6)
- [ ] Load tested (100+ concurrent users)
- [ ] Monitoring dashboards
- [ ] Error alerting
- [ ] Documentation complete
- [ ] Deployed to staging
- [ ] Security audit passed

---

**Current Status:** Core infrastructure complete ✅  
**Next Action:** Implement OAuth flow (Phase 1.1)  
**Estimated to Production:** 6 weeks
