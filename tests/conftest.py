"""
Test configuration for pytest.
Sets up async test environment and database isolation.
"""

import pytest
import os
import tempfile
from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment before running tests."""
    # Use temporary file database for tests
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db.close()
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db.name}"
    
    # Set test webhook secret
    os.environ["WEBHOOK_SECRET"] = "test_secret_key_for_testing"
    
    # Force reload settings
    import importlib
    import app.config
    importlib.reload(app.config)
    
    print(f"Test DB URL: {temp_db.name}")
    
    yield temp_db.name
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except:
        pass


@pytest.fixture(autouse=True)
async def reset_database():
    """Clear database before each test."""
    from app.models import get_db_connection
    
    # Delete all messages before each test
    async with get_db_connection() as db:
        await db.execute("DELETE FROM messages")
        await db.commit()
    
    yield
