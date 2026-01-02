# Lyftr AI - Production Webhook API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

This project originated from a real-world backend challenge inspired by messaging platform workflows and was extended beyond the initial scope to explore production-grade API design, security patterns, and observability in distributed systems.

A containerized FastAPI service demonstrating secure webhook ingestion with cryptographic verification, idempotent message handling, comprehensive observability, and production-ready operational patterns.

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

- [Real-World Context](#real-world-context)
- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Engineering Decisions](#engineering-decisions)
- [Trade-offs & Limitations](#trade-offs--limitations)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Project Background](#project-background)

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

## �️ Engineering Decisions

These decisions reflect deliberate trade-offs between security, reliability, performance, and operational complexity.

### 1. Idempotency Keys for Safe Webhook Retries

**Decision:** Use database-level uniqueness constraints on `message_id` rather than application-level deduplication.

**Rationale:**
- Webhook senders (Twilio, Stripe, etc.) retry on network failures or timeouts
- Without idempotency, retries would create duplicate records
- Database `PRIMARY KEY` provides atomic, race-condition-free enforcement
- Application catches `IntegrityError` and returns `200` for duplicates

**Production impact:**
- Safely handles concurrent retries from distributed webhook senders
- Eliminates need for distributed locks or Redis-based deduplication
- Simpler debugging: duplicate detection is a database constraint violation, not application logic

### 2. Request Signature Verification to Prevent Spoofing

**Decision:** Require HMAC-SHA256 signatures on all webhook requests, validated before any processing.

**Implementation details:**
- Signature computed over raw request body: `HMAC-SHA256(secret, body_bytes)`
- Constant-time comparison via `hmac.compare_digest()` prevents timing attacks
- Invalid/missing signatures rejected with `401` before database access

**Why this matters:**
- Prevents attackers from injecting fake messages without the shared secret
- Protects against replay attacks when combined with timestamp validation
- Industry-standard pattern used by Stripe, GitHub, Shopify webhooks

### 3. Structured Logging for Distributed System Traceability

**Decision:** Emit one JSON log line per request with request ID, latency, and business context.

**Key fields:**
- `request_id`: Unique UUID for tracing across services
- `latency_ms`: Performance debugging
- `message_id`, `dup`, `result`: Business-level context for webhook outcomes

**Production benefits:**
- Easy integration with log aggregation (ELK, Datadog, Splunk)
- Correlation of frontend errors with backend logs via request ID
- Efficient querying with tools like `jq` or cloud logging filters

### 4. Prometheus Metrics for Real-Time Observability

**Decision:** Expose Prometheus-compatible `/metrics` endpoint with request counters and latency histograms.

**Metrics captured:**
- `http_requests_total{method, path, status}`: Track error rates per endpoint
- `webhook_requests_total{result}`: Monitor created vs duplicate vs invalid signature
- `request_latency_ms`: P50/P95/P99 latency analysis

**Why Prometheus:**
- Industry standard for Kubernetes-based deployments
- Enables alerting on SLIs (e.g., "alert if webhook error rate > 5%")
- Grafana integration for real-time dashboards

### 5. SQLite for MVP, PostgreSQL-Ready Architecture

**Decision:** Use SQLite for simplicity, but design schema and queries to be PostgreSQL-compatible.

**Trade-off:**
- SQLite is sufficient for single-instance deployments and < 100k messages
- Schema uses standard SQL types and constraints
- `aiosqlite` provides async interface similar to `asyncpg`

**Migration path:**
- Change `DATABASE_URL` from `sqlite:///` to `postgresql://`
- Add connection pooling for concurrent writes
- Consider partitioning on `ts` for time-series data

### 6. Pagination Design: Offset-Based for Simplicity

**Decision:** Use `LIMIT/OFFSET` pagination with deterministic ordering (`ts ASC, message_id ASC`).

**Trade-off:**
- Simple to implement and understand
- Works well for < 100k rows and moderate page depths
- Slower for deep pagination (e.g., offset=50000)

**Future optimization:**
- Keyset pagination using `WHERE ts > ? OR (ts = ? AND message_id > ?)` for constant-time performance
- Requires cursor-based API contract instead of offset

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

## 🧑‍💻 Project Background

**Origin:** This project was developed to explore production-grade patterns for webhook handling in distributed systems, inspired by real-world challenges in messaging and payment platforms.

**Development approach:**
- **Architecture**: All system design decisions (idempotency strategy, signature verification, observability patterns) were made based on production requirements and industry best practices
- **Implementation**: Modern development workflow using IDE tooling (VSCode, Python extensions) and AI assistance for boilerplate generation, documentation structuring, and test case coverage
- **Ownership**: Security model, error handling strategies, operational patterns, and production readiness analysis reflect hands-on engineering decisions

**Technology choices rationale:**
- **FastAPI**: Async-native framework with automatic OpenAPI docs and excellent performance
- **SQLite → PostgreSQL path**: Start simple, design for migration
- **Prometheus**: Industry standard for Kubernetes deployments
- **HMAC-SHA256**: Widely adopted webhook security pattern

**Testing philosophy:**
- Comprehensive test coverage for all endpoints and edge cases
- Explicit testing of idempotency, signature validation, and error paths
- Property-based testing approach for input validation

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🤝 Acknowledgments

This project demonstrates production-ready webhook handling patterns. The architecture and implementation patterns are applicable to various real-world messaging, payment, and event-driven systems.

---

**Built with FastAPI, Python, and Docker | Production patterns for distributed systems**
