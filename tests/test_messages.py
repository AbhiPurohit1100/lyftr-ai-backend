"""
Test suite for /messages endpoint.
Covers pagination, filtering, and ordering.
"""

import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient
from app.main import app
from app.config import settings


def compute_signature(body: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature of body."""
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


async def seed_message(client: AsyncClient, message: dict):
    """Helper to seed a message via webhook."""
    body = json.dumps(message)
    signature = compute_signature(body, settings.WEBHOOK_SECRET)
    
    await client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )


@pytest.mark.asyncio
async def test_messages_empty():
    """Test /messages returns empty list when no messages exist."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/messages")
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["total"] == 0
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_messages_pagination():
    """Test /messages pagination with limit and offset."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed 5 messages
        for i in range(5):
            message = {
                "message_id": f"page_test_{i}",
                "from": "+919876543210",
                "to": "+14155550100",
                "ts": f"2025-01-15T10:0{i}:00Z",
                "text": f"Message {i}"
            }
            await seed_message(client, message)
        
        # Test limit=2, offset=0
        response = await client.get("/messages?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0
        
        # Test limit=2, offset=2
        response = await client.get("/messages?limit=2&offset=2")
        data = response.json()
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["offset"] == 2


@pytest.mark.asyncio
async def test_messages_filter_by_from():
    """Test /messages filtering by from parameter."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages from different senders
        await seed_message(client, {
            "message_id": "filter_from_1",
            "from": "+911111111111",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "From sender 1"
        })
        await seed_message(client, {
            "message_id": "filter_from_2",
            "from": "+922222222222",
            "to": "+14155550100",
            "ts": "2025-01-15T10:01:00Z",
            "text": "From sender 2"
        })
        
        # Filter by first sender
        response = await client.get("/messages?from=%2B911111111111")
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["from"] == "+911111111111"


@pytest.mark.asyncio
async def test_messages_filter_by_since():
    """Test /messages filtering by since timestamp."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages with different timestamps
        await seed_message(client, {
            "message_id": "filter_since_1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T09:00:00Z",
            "text": "Early message"
        })
        await seed_message(client, {
            "message_id": "filter_since_2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T11:00:00Z",
            "text": "Late message"
        })
        
        # Filter by since=10:00:00
        response = await client.get("/messages?since=2025-01-15T10:00:00Z")
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["message_id"] == "filter_since_2"


@pytest.mark.asyncio
async def test_messages_filter_by_search_text():
    """Test /messages filtering by text search (q parameter)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages with different text
        await seed_message(client, {
            "message_id": "search_1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello world"
        })
        await seed_message(client, {
            "message_id": "search_2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:01:00Z",
            "text": "Goodbye world"
        })
        
        # Search for "Hello"
        response = await client.get("/messages?q=Hello")
        data = response.json()
        assert data["total"] == 1
        assert "Hello" in data["data"][0]["text"]


@pytest.mark.asyncio
async def test_messages_ordering():
    """Test /messages returns results in ts ASC, message_id ASC order."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages in non-sequential order
        await seed_message(client, {
            "message_id": "order_c",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:02:00Z",
            "text": "Third"
        })
        await seed_message(client, {
            "message_id": "order_a",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "First"
        })
        await seed_message(client, {
            "message_id": "order_b",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:01:00Z",
            "text": "Second"
        })
        
        # Get all messages
        response = await client.get("/messages")
        data = response.json()
        
        # Verify ordering
        assert len(data["data"]) >= 3
        messages = [m for m in data["data"] if m["message_id"].startswith("order_")]
        assert messages[0]["message_id"] == "order_a"
        assert messages[1]["message_id"] == "order_b"
        assert messages[2]["message_id"] == "order_c"


@pytest.mark.asyncio
async def test_messages_limit_validation():
    """Test /messages validates limit parameter bounds."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test limit > 100
        response = await client.get("/messages?limit=150")
        assert response.status_code == 422
        
        # Test limit < 1
        response = await client.get("/messages?limit=0")
        assert response.status_code == 422
        
        # Test valid limit
        response = await client.get("/messages?limit=50")
        assert response.status_code == 200
