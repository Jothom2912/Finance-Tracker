#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

echo ""
echo "Monitoring stack started."
echo "Grafana:    http://localhost:3001  (admin/admin)"
echo "Prometheus: http://localhost:9090"
echo "Loki:       http://localhost:3100/ready"
echo "cAdvisor:   http://localhost:8089"
