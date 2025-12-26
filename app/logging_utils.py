"""
Structured JSON logging utilities.
One JSON line per request for easy aggregation and analysis.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any
from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "message_id"):
            log_data["message_id"] = record.message_id
        if hasattr(record, "dup"):
            log_data["dup"] = record.dup
        if hasattr(record, "result"):
            log_data["result"] = record.result
        
        # Add any other extra attributes
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "request_id", "method", "path",
                "status", "latency_ms", "message_id", "dup", "result"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


# Configure logger
logger = logging.getLogger("lyftr_ai")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

# Remove default handlers
logger.handlers.clear()

# Add JSON handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Prevent propagation to root logger
logger.propagate = False


def log_request(log_data: Dict[str, Any]):
    """
    Log a request with structured data.
    
    Args:
        log_data: Dictionary with request metadata
    """
    # Determine log level based on status code
    status = log_data.get("status", 500)
    if status >= 500:
        level = logging.ERROR
    elif status >= 400:
        level = logging.WARNING
    else:
        level = logging.INFO
    
    # Create log record with extra fields
    logger.log(
        level,
        f"{log_data.get('method')} {log_data.get('path')} -> {status}",
        extra=log_data,
    )
