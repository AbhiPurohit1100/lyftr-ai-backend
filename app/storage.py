"""
Database storage operations.
Handles message insertion, retrieval, and statistics.
"""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
import aiosqlite
from app.models import get_db_connection


async def insert_message(
    db: aiosqlite.Connection,
    message_id: str,
    from_msisdn: str,
    to_msisdn: str,
    ts: str,
    text: Optional[str],
) -> bool:
    """
    Insert a message into the database with idempotency.
    
    Args:
        db: Database connection
        message_id: Unique message identifier
        from_msisdn: Sender phone number
        to_msisdn: Recipient phone number
        ts: Message timestamp (ISO-8601)
        text: Message text content
    
    Returns:
        True if message was inserted, False if duplicate
    """
    created_at = datetime.utcnow().isoformat() + "Z"
    
    try:
        await db.execute(
            """
            INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, from_msisdn, to_msisdn, ts, text, created_at),
        )
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        # Duplicate message_id (PRIMARY KEY violation)
        return False


async def get_messages(
    db: aiosqlite.Connection,
    limit: int = 50,
    offset: int = 0,
    from_msisdn: Optional[str] = None,
    since: Optional[str] = None,
    search_text: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    """
    Retrieve messages with pagination and filtering.
    
    Args:
        db: Database connection
        limit: Maximum number of results
        offset: Number of results to skip
        from_msisdn: Filter by sender (exact match)
        since: Filter by timestamp >= since
        search_text: Search in message text (case-insensitive)
    
    Returns:
        Tuple of (messages list, total count)
    """
    # Build WHERE clause
    where_clauses = []
    params = []
    
    if from_msisdn:
        where_clauses.append("from_msisdn = ?")
        params.append(from_msisdn)
    
    if since:
        where_clauses.append("ts >= ?")
        params.append(since)
    
    if search_text:
        where_clauses.append("text LIKE ?")
        params.append(f"%{search_text}%")
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Get total count
    count_query = f"SELECT COUNT(*) FROM messages WHERE {where_sql}"
    cursor = await db.execute(count_query, params)
    row = await cursor.fetchone()
    total = row[0] if row else 0
    
    # Get paginated results with deterministic ordering
    data_query = f"""
        SELECT message_id, from_msisdn AS "from", to_msisdn AS "to", ts, text
        FROM messages
        WHERE {where_sql}
        ORDER BY ts ASC, message_id ASC
        LIMIT ? OFFSET ?
    """
    cursor = await db.execute(data_query, params + [limit, offset])
    rows = await cursor.fetchall()
    
    # Convert rows to dictionaries
    messages = [dict(row) for row in rows]
    
    return messages, total


async def get_stats(db: aiosqlite.Connection) -> Dict:
    """
    Calculate message-level statistics.
    
    Args:
        db: Database connection
    
    Returns:
        Dictionary with statistics
    """
    # Total messages
    cursor = await db.execute("SELECT COUNT(*) FROM messages")
    row = await cursor.fetchone()
    total_messages = row[0] if row else 0
    
    # Unique senders count
    cursor = await db.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages")
    row = await cursor.fetchone()
    senders_count = row[0] if row else 0
    
    # Top senders (up to 10)
    cursor = await db.execute("""
        SELECT from_msisdn AS "from", COUNT(*) AS count
        FROM messages
        GROUP BY from_msisdn
        ORDER BY count DESC, from_msisdn ASC
        LIMIT 10
    """)
    rows = await cursor.fetchall()
    messages_per_sender = [dict(row) for row in rows]
    
    # First and last message timestamps
    cursor = await db.execute("SELECT MIN(ts), MAX(ts) FROM messages")
    row = await cursor.fetchone()
    first_message_ts = row[0] if row and row[0] else None
    last_message_ts = row[1] if row and row[1] else None
    
    return {
        "total_messages": total_messages,
        "senders_count": senders_count,
        "messages_per_sender": messages_per_sender,
        "first_message_ts": first_message_ts,
        "last_message_ts": last_message_ts,
    }


async def check_db_ready() -> bool:
    """
    Check if database is ready (reachable and schema applied).
    
    Returns:
        True if database is ready, False otherwise
    """
    try:
        async with get_db_connection() as db:
            # Check if messages table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            )
            row = await cursor.fetchone()
            return row is not None
    except Exception:
        return False
