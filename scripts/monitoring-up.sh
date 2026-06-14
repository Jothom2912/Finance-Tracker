#!/usr/bin/env bash
set -euo pipefail

echo "Deploying Kubernetes monitoring stack..."
kubectl apply -k k8s/monitoring

echo "Waiting for monitoring deployments..."
kubectl rollout status deployment/prometheus -n finance-tracker --timeout=180s
kubectl rollout status deployment/blackbox-exporter -n finance-tracker --timeout=180s
kubectl rollout status deployment/loki -n finance-tracker --timeout=180s
kubectl rollout status deployment/grafana -n finance-tracker --timeout=180s
kubectl rollout status daemonset/promtail -n finance-tracker --timeout=180s
kubectl rollout status daemonset/cadvisor -n finance-tracker --timeout=180s

echo ""
echo "Monitoring stack is running in Kubernetes."
echo "Open dashboards with these port-forwards:"
echo "  kubectl -n finance-tracker port-forward svc/grafana 3001:3000"
echo "  kubectl -n finance-tracker port-forward svc/prometheus 9090:9090"
echo "  kubectl -n finance-tracker port-forward svc/loki 3100:3100"
echo ""
echo "Grafana:    http://localhost:3001  (admin/admin)"
echo "Prometheus: http://localhost:9090"
echo "Loki:       http://localhost:3100/ready"
