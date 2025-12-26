"""
Database models and initialization.
SQLite schema with idempotency enforcement.
"""

import aiosqlite
from contextlib import asynccontextmanager
from app.config import settings


# Schema definition
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);
"""

# Index for common queries
CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_from_msisdn ON messages(from_msisdn);",
    "CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts);",
    "CREATE INDEX IF NOT EXISTS idx_created_at ON messages(created_at);",
]


async def init_db():
    """
    Initialize database schema.
    Creates tables and indexes if they don't exist.
    """
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    async with aiosqlite.connect(db_path) as db:
        # Create table
        await db.execute(CREATE_TABLE_SQL)
        
        # Create indexes
        for index_sql in CREATE_INDEXES_SQL:
            await db.execute(index_sql)
        
        await db.commit()


@asynccontextmanager
async def get_db_connection():
    """
    Get async database connection context manager.
    
    Usage:
        async with get_db_connection() as db:
            # use db
    """
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
