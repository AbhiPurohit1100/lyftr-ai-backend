#!/bin/bash
# Quick test script to validate the API endpoints

set -e

API_URL="http://localhost:8000"
SECRET="testsecret"

echo "🧪 Testing Lyftr AI Webhook API"
echo "================================"

# Test health endpoints
echo ""
echo "✓ Testing health endpoints..."
curl -sf "$API_URL/health/live" > /dev/null && echo "  ✓ /health/live is OK"
curl -sf "$API_URL/health/ready" > /dev/null && echo "  ✓ /health/ready is OK"

# Test webhook with valid signature
echo ""
echo "✓ Testing /webhook endpoint..."
BODY='{"message_id":"test_1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
SIG=$(python3 compute_signature.py "$SECRET" "$BODY")

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY" \
  "$API_URL/webhook")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ]; then
  echo "  ✓ Valid webhook request accepted (200)"
else
  echo "  ✗ Unexpected status code: $HTTP_CODE"
  exit 1
fi

# Test duplicate (idempotency)
echo ""
echo "✓ Testing idempotency..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY" \
  "$API_URL/webhook")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ]; then
  echo "  ✓ Duplicate message handled correctly (200)"
else
  echo "  ✗ Unexpected status code: $HTTP_CODE"
  exit 1
fi

# Test invalid signature
echo ""
echo "✓ Testing invalid signature..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -H "X-Signature: invalid123" \
  -d "$BODY" \
  "$API_URL/webhook")

if [ "$HTTP_CODE" = "401" ]; then
  echo "  ✓ Invalid signature rejected (401)"
else
  echo "  ✗ Unexpected status code: $HTTP_CODE"
  exit 1
fi

# Test /messages endpoint
echo ""
echo "✓ Testing /messages endpoint..."
curl -sf "$API_URL/messages" | jq . > /dev/null && echo "  ✓ /messages returns valid JSON"

# Test /stats endpoint
echo ""
echo "✓ Testing /stats endpoint..."
curl -sf "$API_URL/stats" | jq . > /dev/null && echo "  ✓ /stats returns valid JSON"

# Test /metrics endpoint
echo ""
echo "✓ Testing /metrics endpoint..."
METRICS=$(curl -sf "$API_URL/metrics")
echo "$METRICS" | grep -q "http_requests_total" && echo "  ✓ Metrics include http_requests_total"
echo "$METRICS" | grep -q "webhook_requests_total" && echo "  ✓ Metrics include webhook_requests_total"

echo ""
echo "================================"
echo "✅ All tests passed!"
