#!/usr/bin/env bash

NAMESPACE="finance-tracker"

echo "Starting Finance Tracker port-forwards..."

PIDS=()

cleanup() {
  echo ""
  echo "Stopping port-forwards..."

  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done

  wait 2>/dev/null || true
  echo "All port-forwards stopped."
}

trap cleanup EXIT INT TERM

start_port_forward() {
  SERVICE_NAME="$1"
  PORT_MAPPING="$2"

  echo "Starting port-forward: svc/$SERVICE_NAME $PORT_MAPPING"
  kubectl -n "$NAMESPACE" port-forward "svc/$SERVICE_NAME" "$PORT_MAPPING" &

  PIDS+=($!)
  sleep 0.3
}

start_port_forward "frontend" "5173:3000"
start_port_forward "user-service" "8001:8001"
start_port_forward "transaction-service" "8002:8002"
start_port_forward "budget-service" "8003:8003"
start_port_forward "account-service" "8004:8003"
start_port_forward "categorization-service" "8005:8005"
start_port_forward "goal-service" "8006:8006"
start_port_forward "ai-service" "8007:8004"
start_port_forward "banking-service" "8009:8009"
start_port_forward "gateway-service" "8010:8010"
start_port_forward "rabbitmq" "15672:15672"
start_port_forward "grafana" "3001:3000"
start_port_forward "prometheus" "9090:9090"
start_port_forward "loki" "3100:3100"
start_port_forward "blackbox-exporter" "9115:9115"
start_port_forward "cadvisor" "8089:8080"
start_port_forward "saga-service" "8011:8011"

echo ""
echo "Port-forwards started:"
echo "Frontend:     http://localhost:5173"
echo "Gateway/GQL:  http://localhost:8010/api/v1/graphql"
echo "RabbitMQ:     http://localhost:15672  guest / guest"
echo "Grafana:      http://localhost:3001  admin / admin"
echo "Prometheus:   http://localhost:9090"
echo "Saga:         http://localhost:8011/health"

echo ""
echo "Press CTRL+C to stop all port-forwards."

wait