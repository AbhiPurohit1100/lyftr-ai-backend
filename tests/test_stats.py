"""
Test suite for /stats endpoint.
Covers statistics calculation and correctness.
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
async def test_stats_empty():
    """Test /stats with no messages returns zeros and nulls."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 0
    assert data["senders_count"] == 0
    assert data["messages_per_sender"] == []
    assert data["first_message_ts"] is None
    assert data["last_message_ts"] is None


@pytest.mark.asyncio
async def test_stats_with_messages():
    """Test /stats calculates correct statistics."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages from different senders
        await seed_message(client, {
            "message_id": "stats_1",
            "from": "+911111111111",
            "to": "+14155550100",
            "ts": "2025-01-15T09:00:00Z",
            "text": "Message 1"
        })
        await seed_message(client, {
            "message_id": "stats_2",
            "from": "+911111111111",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Message 2"
        })
        await seed_message(client, {
            "message_id": "stats_3",
            "from": "+922222222222",
            "to": "+14155550100",
            "ts": "2025-01-15T11:00:00Z",
            "text": "Message 3"
        })
        
        # Get stats
        response = await client.get("/stats")
        data = response.json()
        
        # Verify statistics
        assert data["total_messages"] == 3
        assert data["senders_count"] == 2
        assert len(data["messages_per_sender"]) == 2
        
        # Verify messages_per_sender sorted by count desc
        assert data["messages_per_sender"][0]["count"] == 2
        assert data["messages_per_sender"][0]["from"] == "+911111111111"
        assert data["messages_per_sender"][1]["count"] == 1
        
        # Verify timestamps
        assert data["first_message_ts"] == "2025-01-15T09:00:00Z"
        assert data["last_message_ts"] == "2025-01-15T11:00:00Z"


@pytest.mark.asyncio
async def test_stats_top_senders_limit():
    """Test /stats returns maximum 10 top senders."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages from 15 different senders
        for i in range(15):
            await seed_message(client, {
                "message_id": f"stats_limit_{i}",
                "from": f"+91{str(i).zfill(10)}",
                "to": "+14155550100",
                "ts": "2025-01-15T10:00:00Z",
                "text": f"Message from sender {i}"
            })
        
        # Get stats
        response = await client.get("/stats")
        data = response.json()
        
        # Verify only 10 senders returned
        assert data["total_messages"] == 15
        assert data["senders_count"] == 15
        assert len(data["messages_per_sender"]) == 10


@pytest.mark.asyncio
async def test_stats_messages_per_sender_sum():
    """Test messages_per_sender counts sum up correctly."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed messages with varying counts per sender
        for i in range(3):
            await seed_message(client, {
                "message_id": f"stats_sum_1_{i}",
                "from": "+911111111111",
                "to": "+14155550100",
                "ts": f"2025-01-15T10:0{i}:00Z",
                "text": f"From sender 1, message {i}"
            })
        
        for i in range(2):
            await seed_message(client, {
                "message_id": f"stats_sum_2_{i}",
                "from": "+922222222222",
                "to": "+14155550100",
                "ts": f"2025-01-15T11:0{i}:00Z",
                "text": f"From sender 2, message {i}"
            })
        
        # Get stats
        response = await client.get("/stats")
        data = response.json()
        
        # Calculate sum
        total_from_senders = sum(s["count"] for s in data["messages_per_sender"])
        assert total_from_senders == data["total_messages"]
