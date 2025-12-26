#!/usr/bin/env python3
"""
Helper script to compute HMAC-SHA256 signature for webhook testing.
Usage: python compute_signature.py <secret> <json_body>
"""

import sys
import hmac
import hashlib


def compute_signature(secret: str, body: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compute_signature.py <secret> <json_body>")
        print('\nExample:')
        print('  python compute_signature.py "testsecret" \'{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}\'')
        sys.exit(1)
    
    secret = sys.argv[1]
    body = sys.argv[2]
    
    signature = compute_signature(secret, body)
    print(signature)
