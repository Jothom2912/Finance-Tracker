docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

Write-Host ""
Write-Host "Monitoring stack started."
Write-Host "Grafana:    http://localhost:3001  (admin/admin)"
Write-Host "Prometheus: http://localhost:9090"
Write-Host "Loki:       http://localhost:3100/ready"
Write-Host "cAdvisor:   http://localhost:8089"
