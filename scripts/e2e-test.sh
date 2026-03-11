#!/usr/bin/env bash
set -euo pipefail

echo "=== Building and starting services ==="
docker compose up -d --build --wait

echo "=== Waiting for services to stabilise ==="
sleep 5

echo "=== Running e2e tests ==="
python -m pytest tests/e2e/ -v -m e2e

echo "=== Tearing down ==="
docker compose down -v

echo "=== Done ==="
