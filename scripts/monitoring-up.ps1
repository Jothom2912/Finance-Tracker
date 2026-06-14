$ErrorActionPreference = "Stop"

Write-Host "Deploying Kubernetes monitoring stack..." -ForegroundColor Cyan
kubectl apply -k k8s/monitoring

Write-Host "Waiting for monitoring deployments..." -ForegroundColor Cyan
kubectl rollout status deployment/prometheus -n finance-tracker --timeout=180s
kubectl rollout status deployment/blackbox-exporter -n finance-tracker --timeout=180s
kubectl rollout status deployment/loki -n finance-tracker --timeout=180s
kubectl rollout status deployment/grafana -n finance-tracker --timeout=180s
kubectl rollout status daemonset/promtail -n finance-tracker --timeout=180s
kubectl rollout status daemonset/cadvisor -n finance-tracker --timeout=180s

Write-Host ""
Write-Host "Monitoring stack is running in Kubernetes." -ForegroundColor Green
Write-Host "Open dashboards with these port-forwards:"
Write-Host "  kubectl -n finance-tracker port-forward svc/grafana 3001:3000"
Write-Host "  kubectl -n finance-tracker port-forward svc/prometheus 9090:9090"
Write-Host "  kubectl -n finance-tracker port-forward svc/loki 3100:3100"
Write-Host ""
Write-Host "Grafana:    http://localhost:3001  (admin/admin)" -ForegroundColor Green
Write-Host "Prometheus: http://localhost:9090" -ForegroundColor Green
Write-Host "Loki:       http://localhost:3100/ready" -ForegroundColor Green
