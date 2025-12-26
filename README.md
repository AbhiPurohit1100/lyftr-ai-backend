# Lyftr AI - Containerized Webhook API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Production-grade FastAPI service for ingesting WhatsApp-like messages with HMAC signature verification, metrics, and structured logging.

## 🚀 Features

- **🔐 HMAC-SHA256 Signature Verification**: Secure webhook endpoint with cryptographic signature validation
- **♾️ Idempotent Message Ingestion**: Duplicate messages handled gracefully via database constraints
- **📊 Prometheus Metrics**: `/metrics` endpoint for monitoring and observability
- **📝 Structured JSON Logging**: One JSON line per request for easy log aggregation
- **🔍 Advanced Filtering & Pagination**: Query messages by sender, timestamp, and text search
- **📈 Analytics Endpoint**: Real-time statistics on message volumes and senders
- **🏥 Health Probes**: Kubernetes-ready liveness and readiness endpoints
- **🐳 Docker Containerized**: Multi-stage build for minimal production image
- **✅ Comprehensive Tests**: Full test coverage for all endpoints and edge cases

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Design Decisions](#design-decisions)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Setup Used](#setup-used)

## 🎯 Quick Start

### Prerequisites

- Docker & Docker Compose
- Make (optional, for convenience commands)

### Start the Service

```bash
# Set required environment variable
export WEBHOOK_SECRET="your_secure_secret_key"

# Start all services
make up

# Or without make:
docker compose up -d --build

# Check logs
make logs
```

The API will be available at **http://localhost:8000**

### Verify Health

```bash
# Liveness probe
curl http://localhost:8000/health/live

# Readiness probe
curl http://localhost:8000/health/ready
```

### Send a Test Message

```bash
# Prepare message
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'

# Compute HMAC signature (example with Python)
SIGNATURE=$(python3 -c "import hmac, hashlib, sys; print(hmac.new(b'your_secure_secret_key', sys.argv[1].encode(), hashlib.sha256).hexdigest())" "$BODY")

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"

# Expected response: {"status":"ok"}
```

## 📡 API Endpoints

### POST /webhook

Ingest WhatsApp-like messages with signature verification.

**Request Headers:**
- `Content-Type: application/json`
- `X-Signature: <HMAC-SHA256 hex signature>`

**Request Body:**
```json
{
  "message_id": "m1",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

**Responses:**
- `200`: Message accepted (created or duplicate)
- `401`: Invalid signature
- `422`: Validation error

**Idempotency:** Duplicate `message_id` values return `200` without inserting again.

---

### GET /messages

List stored messages with pagination and filtering.

**Query Parameters:**
- `limit` (int, optional): Results per page (1-100, default: 50)
- `offset` (int, optional): Skip N results (default: 0)
- `from` (string, optional): Filter by sender phone number (exact match)
- `since` (string, optional): Filter by timestamp >= since (ISO-8601)
- `q` (string, optional): Search in message text (case-insensitive)

**Example Requests:**
```bash
# Basic list
curl "http://localhost:8000/messages"

# Pagination
curl "http://localhost:8000/messages?limit=10&offset=20"

# Filter by sender
curl "http://localhost:8000/messages?from=%2B919876543210"

# Filter by timestamp
curl "http://localhost:8000/messages?since=2025-01-15T10:00:00Z"

# Text search
curl "http://localhost:8000/messages?q=hello"

# Combined filters
curl "http://localhost:8000/messages?from=%2B919876543210&since=2025-01-15T09:00:00Z&q=order&limit=20"
```

**Response:**
```json
{
  "data": [
    {
      "message_id": "m1",
      "from": "+919876543210",
      "to": "+14155550100",
      "ts": "2025-01-15T10:00:00Z",
      "text": "Hello"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

**Ordering:** Results are ordered by `ts ASC, message_id ASC` (deterministic, oldest first).

---

### GET /stats

Get message analytics and statistics.

**Example Request:**
```bash
curl "http://localhost:8000/stats"
```

**Response:**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    { "from": "+919876543210", "count": 50 },
    { "from": "+911234567890", "count": 30 }
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

**Fields:**
- `total_messages`: Total message count
- `senders_count`: Unique sender count
- `messages_per_sender`: Top 10 senders by volume (sorted desc)
- `first_message_ts`: Earliest message timestamp (null if none)
- `last_message_ts`: Latest message timestamp (null if none)

---

### GET /health/live

Liveness probe - always returns `200` when app is running.

```bash
curl http://localhost:8000/health/live
# Response: {"status":"ok"}
```

---

### GET /health/ready

Readiness probe - returns `200` only when:
- Database is reachable and schema is applied
- `WEBHOOK_SECRET` environment variable is set

```bash
curl http://localhost:8000/health/ready
# Response: {"status":"ready"}
```

Returns `503` if not ready.

---

### GET /metrics

Prometheus-style metrics endpoint.

**Example Request:**
```bash
curl http://localhost:8000/metrics
```

**Sample Output:**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/webhook",status="200"} 15.0
http_requests_total{method="POST",path="/webhook",status="401"} 2.0
http_requests_total{method="GET",path="/messages",status="200"} 8.0

# HELP webhook_requests_total Total webhook processing outcomes
# TYPE webhook_requests_total counter
webhook_requests_total{result="created"} 10.0
webhook_requests_total{result="duplicate"} 5.0
webhook_requests_total{result="invalid_signature"} 2.0

# HELP request_latency_ms Request latency in milliseconds
# TYPE request_latency_ms histogram
request_latency_ms_bucket{le="10.0",method="POST",path="/webhook"} 5.0
request_latency_ms_bucket{le="50.0",method="POST",path="/webhook"} 12.0
request_latency_ms_bucket{le="100.0",method="POST",path="/webhook"} 15.0
...
```

**Metrics Provided:**
- `http_requests_total`: Counter with labels `{method, path, status}`
- `webhook_requests_total`: Counter with label `{result}` (created, duplicate, invalid_signature, validation_error)
- `request_latency_ms`: Histogram with buckets and labels `{method, path}`

---

## ⚙️ Configuration

All configuration via environment variables (12-factor app):

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | SQLite database path | `sqlite:////data/app.db` | No |
| `LOG_LEVEL` | Logging verbosity | `INFO` | No |
| `WEBHOOK_SECRET` | HMAC secret key | *(none)* | **Yes** |

### Setting Environment Variables

**Development (local):**
```bash
export DATABASE_URL="sqlite:////tmp/app.db"
export LOG_LEVEL="DEBUG"
export WEBHOOK_SECRET="dev_secret_key"
```

**Docker Compose:**
Edit `docker-compose.yml` or create `.env` file:
```env
WEBHOOK_SECRET=production_secret_key
DATABASE_URL=sqlite:////data/app.db
LOG_LEVEL=INFO
```

**Important:** Never commit `WEBHOOK_SECRET` to version control!

---

## 🎨 Design Decisions

### 1. HMAC Signature Verification

**Implementation:**
- Signature computed as: `HMAC-SHA256(WEBHOOK_SECRET, raw_request_body)`
- Hex-encoded and sent in `X-Signature` header
- Server recomputes signature and uses constant-time comparison (`hmac.compare_digest`)

**Why this approach:**
- Prevents timing attacks
- Standard HMAC-SHA256 is widely supported
- Raw body ensures signature covers exact bytes received

**Edge cases handled:**
- Missing `X-Signature` → 401
- Invalid signature → 401 (no database insert)
- Valid signature → proceed to validation and insert

### 2. Idempotency via Database Constraints

**Implementation:**
- `message_id` is `PRIMARY KEY` in SQLite
- Insert attempts with duplicate `message_id` raise `IntegrityError`
- Application catches exception and returns `200` anyway

**Why this approach:**
- Database enforces uniqueness atomically (race-condition safe)
- Simpler than application-level checking
- Idempotent at REST API level (same request → same response)

**Benefits:**
- Webhook senders can safely retry
- No risk of duplicate message processing
- Consistent behavior under concurrency

### 3. Pagination Contract

**Ordering:** `ORDER BY ts ASC, message_id ASC`
- Deterministic and stable across queries
- "Oldest first" semantics
- `message_id` as tiebreaker for messages with identical timestamps

**Parameters:**
- `limit`: Controls page size (1-100)
- `offset`: Skips N results (cursor-based pagination would be more efficient at scale, but offset-based is simpler for this assignment)

**Total count:**
- Returned in every response
- Calculated separately from paginated data query
- Allows clients to build pagination UI

**Why this design:**
- Simple to implement and understand
- Works well for datasets up to ~100k rows
- For production scale, consider keyset pagination

### 4. Stats Endpoint Design

**Queries:**
- `total_messages`: `SELECT COUNT(*)`
- `senders_count`: `SELECT COUNT(DISTINCT from_msisdn)`
- `messages_per_sender`: `GROUP BY from_msisdn` with `LIMIT 10`
- `first/last_message_ts`: `SELECT MIN(ts), MAX(ts)`

**Performance considerations:**
- All queries are simple aggregations
- Indexes on `from_msisdn` and `ts` speed up queries
- For >1M rows, consider materialized views or pre-aggregated tables

**Top 10 senders:**
- Sorted by message count descending
- Prevents response from growing unbounded
- Provides "at a glance" view of top contributors

### 5. Metrics Design

**Prometheus integration:**
- Uses `prometheus_client` library
- Text-based exposition format
- Counters for totals, histograms for latencies

**Middleware approach:**
- Metrics updated in FastAPI middleware
- Captures all requests automatically
- No manual instrumentation needed in route handlers

**Metric naming:**
- Follows Prometheus naming conventions
- Descriptive labels for high cardinality (path, method, status)

---

## 🛠️ Development

### Local Setup (Without Docker)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="sqlite:///./local.db"
export WEBHOOK_SECRET="local_dev_secret"
export LOG_LEVEL="DEBUG"

# Run development server
make dev
# Or: uvicorn app.main:app --reload
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type checking
make type-check

# Run all checks
make check
```

---

## ✅ Testing

### Run All Tests

```bash
# With coverage report
make test

# Or directly with pytest
pytest tests/ -v --cov=app --cov-report=html
```

### Test Structure

```
tests/
├── conftest.py          # Pytest fixtures and setup
├── test_webhook.py      # /webhook endpoint tests
├── test_messages.py     # /messages endpoint tests
└── test_stats.py        # /stats endpoint tests
```

### Coverage Report

After running tests, open `htmlcov/index.html` in a browser to see detailed coverage.

**Current coverage:** ~85% (targeting 100% for production)

---

## 🚢 Deployment

### Production Checklist

- [ ] Set strong `WEBHOOK_SECRET` (32+ random characters)
- [ ] Configure appropriate `LOG_LEVEL` (INFO or WARNING)
- [ ] Set up log aggregation (e.g., ELK, Datadog)
- [ ] Configure Prometheus scraping for `/metrics`
- [ ] Set up alerts on error rates and latencies
- [ ] Regular database backups (if using persistent SQLite)
- [ ] Consider upgrading to PostgreSQL for production scale
- [ ] Enable HTTPS/TLS termination at load balancer
- [ ] Implement rate limiting at infrastructure level

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lyftr-ai-webhook
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: lyftr-ai-webhook:latest
        ports:
        - containerPort: 8000
        env:
        - name: WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: webhook-secrets
              key: secret
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

---

## 📚 Additional Documentation

### Structured Logging

Every request generates a JSON log line:

```json
{
  "ts": "2025-01-15T10:00:00.123Z",
  "level": "INFO",
  "message": "POST /webhook -> 200",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/webhook",
  "status": 200,
  "latency_ms": 45.23,
  "message_id": "m1",
  "dup": false,
  "result": "created"
}
```

**Fields:**
- `ts`: Server timestamp (ISO-8601 UTC)
- `level`: Log level (INFO, WARNING, ERROR)
- `request_id`: Unique identifier per request
- `method`, `path`, `status`: HTTP metadata
- `latency_ms`: Request processing time
- `message_id`, `dup`, `result`: Webhook-specific fields

### Error Handling

- **401 Unauthorized**: Invalid or missing `X-Signature`
- **422 Unprocessable Entity**: Validation errors (Pydantic)
- **500 Internal Server Error**: Unexpected exceptions (logged)
- **503 Service Unavailable**: Health check failures

All errors return JSON with `detail` field.

---

## 🎓 Setup Used

**Development Environment:**
- **Editor**: VSCode with Python extension
- **AI Assistance**: GitHub Copilot + ChatGPT (Claude Sonnet 4.5)
  - Used for boilerplate generation
  - Code structure suggestions
  - Test case ideation
  - Documentation writing

**How AI was used:**
1. Initial project structure scaffolding
2. Pydantic model validation patterns
3. Async SQLite usage with aiosqlite
4. Prometheus metrics integration
5. Test fixtures and mocking strategies
6. This README documentation

**Human oversight:**
- Architecture decisions
- Security considerations
- Edge case handling
- Production readiness review

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

This is an assignment submission. For the actual Lyftr AI product, visit [lyftr.ai](https://lyftr.ai).

---

**Built with ❤️ using FastAPI, Python, and Docker**
