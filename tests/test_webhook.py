"""
Test suite for /webhook endpoint.
Covers signature verification, validation, and idempotency.
"""

import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient
from app.main import app
from app.config import settings


@pytest.fixture
def valid_message():
    """Sample valid message payload."""
    return {
        "message_id": "test_msg_1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello, this is a test message"
    }


def compute_signature(body: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature of body."""
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


@pytest.mark.asyncio
async def test_webhook_missing_signature(valid_message):
    """Test webhook without X-Signature header returns 401."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            json=valid_message,
        )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid signature"}


@pytest.mark.asyncio
async def test_webhook_invalid_signature(valid_message):
    """Test webhook with invalid signature returns 401."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            json=valid_message,
            headers={"X-Signature": "invalid_signature_123"}
        )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid signature"}


@pytest.mark.asyncio
async def test_webhook_valid_signature_success(valid_message):
    """Test webhook with valid signature inserts message successfully."""
    body = json.dumps(valid_message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_idempotency(valid_message):
    """Test duplicate message_id returns 200 without inserting again."""
    body = json.dumps(valid_message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First request - should insert
        response1 = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        assert response1.status_code == 200
        
        # Second request - should be idempotent
        response2 = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        assert response2.status_code == 200
        assert response2.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_invalid_phone_format():
    """Test webhook with invalid phone number format returns 422."""
    message = {
        "message_id": "test_invalid_phone",
        "from": "919876543210",  # Missing + prefix
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Test"
    }
    body = json.dumps(message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_invalid_timestamp():
    """Test webhook with invalid timestamp format returns 422."""
    message = {
        "message_id": "test_invalid_ts",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15 10:00:00",  # Missing Z suffix
        "text": "Test"
    }
    body = json.dumps(message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_text_too_long():
    """Test webhook with text exceeding 4096 characters returns 422."""
    message = {
        "message_id": "test_long_text",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "x" * 5000  # Exceeds 4096 limit
    }
    body = json.dumps(message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_missing_required_field():
    """Test webhook with missing required field returns 422."""
    message = {
        "message_id": "test_missing_field",
        "from": "+919876543210",
        # Missing "to" field
        "ts": "2025-01-15T10:00:00Z",
        "text": "Test"
    }
    body = json.dumps(message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
    
    assert response.status_code == 422
