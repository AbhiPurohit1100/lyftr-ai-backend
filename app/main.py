"""
FastAPI main application for Lyftr AI Webhook API.
Production-grade implementation with HMAC verification, metrics, and structured logging.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator
import hmac
import hashlib

from app.config import settings
from app.models import init_db, get_db_connection
from app.storage import (
    insert_message,
    get_messages,
    get_stats,
    check_db_ready,
)
from app.logging_utils import logger, log_request
from app.metrics import (
    http_requests_total,
    webhook_requests_total,
    request_latency_histogram,
    generate_metrics,
)


# Pydantic models for request validation
class WebhookMessage(BaseModel):
    """Webhook message schema with validation."""
    
    message_id: str = Field(..., min_length=1, description="Unique message identifier")
    from_: str = Field(..., alias="from", description="Sender phone number in E.164 format")
    to: str = Field(..., description="Recipient phone number in E.164 format")
    ts: str = Field(..., description="ISO-8601 UTC timestamp with Z suffix")
    text: Optional[str] = Field(None, max_length=4096, description="Message text content")

    @field_validator("from_", "to")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        """Validate E.164 phone number format: +<digits>"""
        if not v.startswith("+"):
            raise ValueError("Phone number must start with +")
        if not v[1:].isdigit():
            raise ValueError("Phone number must contain only digits after +")
        return v

    @field_validator("ts")
    @classmethod
    def validate_iso8601(cls, v: str) -> str:
        """Validate ISO-8601 UTC timestamp with Z suffix."""
        if not v.endswith("Z"):
            raise ValueError("Timestamp must end with Z (UTC)")
        # Basic format check: YYYY-MM-DDTHH:MM:SSZ
        try:
            from datetime import datetime
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid ISO-8601 timestamp format")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Starting Lyftr AI Webhook API")
    
    # Validate WEBHOOK_SECRET is set
    if not settings.WEBHOOK_SECRET:
        logger.error("WEBHOOK_SECRET environment variable is not set!")
        raise RuntimeError("WEBHOOK_SECRET must be set")
    
    # Initialize database
    await init_db()
    logger.info(f"Database initialized at {settings.DATABASE_URL}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Lyftr AI Webhook API")


# Initialize FastAPI app
app = FastAPI(
    title="Lyftr AI Webhook API",
    description="Production-grade WhatsApp-like webhook ingestion service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def logging_and_metrics_middleware(request: Request, call_next):
    """
    Middleware for request logging and metrics collection.
    Tracks latency, HTTP status, and generates structured JSON logs.
    """
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Start timing
    start_time = time.time()
    
    # Process request
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            "Unhandled exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error": str(exc),
            },
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    
    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000
    
    # Update metrics
    http_requests_total.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    ).inc()
    
    request_latency_histogram.labels(
        method=request.method,
        path=request.url.path,
    ).observe(latency_ms)
    
    # Log request
    log_data = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "latency_ms": round(latency_ms, 2),
    }
    
    # Add webhook-specific fields if available
    if hasattr(request.state, "webhook_result"):
        log_data.update(request.state.webhook_result)
    
    log_request(log_data)
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    return response


def verify_signature(body: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature of request body.
    
    Args:
        body: Raw request body bytes
        signature: Hex-encoded signature from X-Signature header
    
    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@app.post("/webhook", status_code=200)
async def webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """
    Ingest WhatsApp-like messages with HMAC signature verification.
    
    - Validates X-Signature header using HMAC-SHA256
    - Ensures idempotency via message_id uniqueness
    - Returns 401 for invalid signatures
    - Returns 422 for validation errors
    - Returns 200 for successful inserts and duplicates
    """
    result = "unknown"
    message_id = None
    is_duplicate = False
    
    try:
        # Read raw body for signature verification
        body = await request.body()
        
        # Verify signature
        if not x_signature:
            result = "invalid_signature"
            webhook_requests_total.labels(result=result).inc()
            logger.error("Missing X-Signature header", extra={"request_id": request.state.request_id})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid signature",
            )
        
        if not verify_signature(body, x_signature):
            result = "invalid_signature"
            webhook_requests_total.labels(result=result).inc()
            logger.error(
                "Invalid signature",
                extra={"request_id": request.state.request_id, "signature": x_signature},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid signature",
            )
        
        # Parse and validate JSON
        try:
            # Parse body as JSON
            import json
            data = json.loads(body)
            message = WebhookMessage(**data)
            message_id = message.message_id
        except Exception as e:
            result = "validation_error"
            webhook_requests_total.labels(result=result).inc()
            logger.error(
                "Validation error",
                extra={"request_id": request.state.request_id, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )
        
        # Insert message (idempotent)
        async with get_db_connection() as db:
            was_inserted = await insert_message(
                db,
                message_id=message.message_id,
                from_msisdn=message.from_,
                to_msisdn=message.to,
                ts=message.ts,
                text=message.text,
            )
            
            if was_inserted:
                result = "created"
                is_duplicate = False
            else:
                result = "duplicate"
                is_duplicate = True
        
        webhook_requests_total.labels(result=result).inc()
        
        # Store webhook result for logging middleware
        request.state.webhook_result = {
            "message_id": message_id,
            "dup": is_duplicate,
            "result": result,
        }
        
        return {"status": "ok"}
    
    except HTTPException:
        # Re-raise HTTP exceptions
        request.state.webhook_result = {
            "message_id": message_id,
            "dup": is_duplicate,
            "result": result,
        }
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        result = "error"
        webhook_requests_total.labels(result=result).inc()
        logger.error(
            "Unexpected error in webhook",
            extra={
                "request_id": request.state.request_id,
                "error": str(e),
                "message_id": message_id,
            },
        )
        request.state.webhook_result = {
            "message_id": message_id,
            "dup": is_duplicate,
            "result": result,
        }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@app.get("/messages")
async def list_messages(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    from_: Optional[str] = Query(None, alias="from", description="Filter by sender phone number"),
    since: Optional[str] = Query(None, description="Filter by timestamp (ISO-8601)"),
    q: Optional[str] = Query(None, description="Search in message text"),
):
    """
    List stored messages with pagination and filtering.
    
    - Supports pagination via limit and offset
    - Filters: from (exact match), since (timestamp >=), q (text search)
    - Ordered by ts ASC, message_id ASC
    - Returns total count of matching records
    """
    async with get_db_connection() as db:
        messages, total = await get_messages(
            db,
            limit=limit,
            offset=offset,
            from_msisdn=from_,
            since=since,
            search_text=q,
        )
    
    return {
        "data": messages,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/stats")
async def get_statistics():
    """
    Provide message-level analytics.
    
    Returns:
        - total_messages: Total number of messages
        - senders_count: Number of unique senders
        - messages_per_sender: Top 10 senders by message count
        - first_message_ts: Timestamp of first message
        - last_message_ts: Timestamp of last message
    """
    async with get_db_connection() as db:
        stats = await get_stats(db)
    
    return stats


@app.get("/health/live")
async def health_live():
    """
    Liveness probe: always returns 200 when app is running.
    """
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """
    Readiness probe: returns 200 only if:
    - Database is reachable and schema is applied
    - WEBHOOK_SECRET is set
    """
    # Check WEBHOOK_SECRET
    if not settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WEBHOOK_SECRET not configured",
        )
    
    # Check database
    is_ready = await check_db_ready()
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready",
        )
    
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """
    Prometheus-style metrics endpoint.
    
    Exposes:
    - http_requests_total: Counter of HTTP requests by method, path, status
    - webhook_requests_total: Counter of webhook processing outcomes
    - request_latency_ms: Histogram of request latencies
    """
    return generate_metrics()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,  # Disable uvicorn's default logging
    )
