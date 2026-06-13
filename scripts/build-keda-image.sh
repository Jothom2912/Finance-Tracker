#!/usr/bin/env bash
set -euo pipefail

echo "Building serverless KEDA job image..."
docker build -t finance-tracker/serverless-health-job:local -f services/serverless-health-job/Dockerfile .
echo "Done. Built finance-tracker/serverless-health-job:local"
