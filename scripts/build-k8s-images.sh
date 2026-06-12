#!/usr/bin/env bash
set -euo pipefail

docker build -t finance-tracker/monolith:local -f services/monolith/Dockerfile .
docker build -t finance-tracker/user-service:local -f services/user-service/Dockerfile .
docker build -t finance-tracker/transaction-service:local -f services/transaction-service/Dockerfile .
docker build -t finance-tracker/account-service:local -f services/account-service/Dockerfile .
docker build -t finance-tracker/categorization-service:local -f services/categorization-service/Dockerfile .
docker build -t finance-tracker/budget-service:local -f services/budget-service/Dockerfile .
docker build -t finance-tracker/goal-service:local -f services/goal-service/Dockerfile .
docker build -t finance-tracker/ai-service:local -f services/ai-service/Dockerfile .

if [ -f services/frontend/Dockerfile ]; then
  docker build -t finance-tracker/frontend:local -f services/frontend/Dockerfile .
else
  echo "Skipping frontend image. Copy frontend.Dockerfile to services/frontend/Dockerfile if needed."
fi
