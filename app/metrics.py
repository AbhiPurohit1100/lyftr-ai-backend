"""
Prometheus metrics collection and exposition.
Tracks HTTP requests, webhook outcomes, and request latencies.
"""

from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from prometheus_client.core import CollectorRegistry


# Create custom registry to avoid conflicts
# (In production, you might want to use the default REGISTRY)

# HTTP request counter with labels
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=REGISTRY,
)

# Webhook processing outcome counter
webhook_requests_total = Counter(
    "webhook_requests_total",
    "Total webhook processing outcomes",
    ["result"],
    registry=REGISTRY,
)

# Request latency histogram with buckets
request_latency_histogram = Histogram(
    "request_latency_ms",
    "Request latency in milliseconds",
    ["method", "path"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    registry=REGISTRY,
)


def generate_metrics() -> str:
    """
    Generate Prometheus-style metrics in text format.
    
    Returns:
        String in Prometheus exposition format
    """
    return generate_latest(REGISTRY).decode("utf-8")
