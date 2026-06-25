#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Basic load test against the running API.
# Requires: curl, jq
# Usage: API_KEY=your-key bash scripts/load-test.sh

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
API_KEY="${API_KEY:?Set API_KEY env var}"
CONCURRENCY="${CONCURRENCY:-10}"
REQUESTS="${REQUESTS:-100}"

echo "Load test: $REQUESTS requests, $CONCURRENCY concurrent"
echo "Target: $API_BASE/health/live"

# Use curl in parallel to hammer the health endpoint
success=0
fail=0

for i in $(seq 1 "$REQUESTS"); do
  (
    status=$(curl -s -o /dev/null -w "%{http_code}" \
      -H "X-API-Key: $API_KEY" \
      "$API_BASE/health/live")
    echo "$status"
  ) &
  # Limit concurrency
  if (( i % CONCURRENCY == 0 )); then
    wait
  fi
done
wait

echo "Done. Check output above for HTTP status codes."
echo "Phase 9 will add proper load testing with k6 or locust."
