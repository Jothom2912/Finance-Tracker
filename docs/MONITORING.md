# Monitoring and logging

Finance Tracker now runs the monitoring stack **inside Kubernetes**. The previous `docker-compose.monitoring.yml` file can still be used for local Docker-only development, but the exam/demo setup should use the Kubernetes manifests in `k8s/monitoring`.

## Tools

* **Prometheus** collects probe and container metrics.
* **Blackbox Exporter** checks whether application services and infrastructure components are reachable through Kubernetes Service DNS.
* **Grafana** visualizes service health, response time, Kubernetes pod CPU/memory and logs.
* **Loki** stores logs.
* **Promtail** runs as a Kubernetes DaemonSet and collects pod logs from `/var/log/pods`.
* **cAdvisor** runs as a Kubernetes DaemonSet and exposes container/pod CPU and memory metrics.

## Why this setup was chosen

The backend services already expose `/health` endpoints. To avoid risky code changes close to delivery, Prometheus uses Blackbox Exporter to probe those endpoints instead of adding custom metrics code to every service.

The important change is that monitoring is no longer pointed at Docker Compose containers. Prometheus now probes Kubernetes Services such as `user-service:8001`, `transaction-service:8002` and `rabbitmq:5672` from inside the `finance-tracker` namespace. Promtail reads Kubernetes pod logs instead of using the Docker socket.

This gives a useful operational overview while keeping the implementation simple:

* service up/down status
* health-check response time
* infrastructure connectivity checks
* Kubernetes pod CPU usage
* Kubernetes pod memory usage
* centralized Kubernetes pod logs

## Kubernetes files

|Area|Files|
|-|-|
|Kubernetes manifests|`k8s/monitoring/*.yaml`|
|Kubernetes monitoring config|`k8s/monitoring/config/**`|
|Source Prometheus config|`monitoring/prometheus/prometheus.k8s.yml`|
|Source Promtail config|`monitoring/promtail/promtail-config.k8s.yml`|
|Grafana dashboard source|`monitoring/grafana/dashboards/finance-tracker-overview.json`|

The root `k8s/kustomization.yaml` includes the monitoring folder, so the full application and monitoring stack can be deployed together with:

```bash
kubectl apply -k k8s
```

You can also deploy/redeploy only the monitoring stack:

```bash
kubectl apply -k k8s/monitoring
```

Or use the helper script:

```bash
./scripts/monitoring-up.sh
```

On Windows PowerShell:

```powershell
./scripts/monitoring-up.ps1
```

## Open the tools

Use port-forwarding from your machine to the Kubernetes Services:

```bash
kubectl -n finance-tracker port-forward svc/grafana 3001:3000
kubectl -n finance-tracker port-forward svc/prometheus 9090:9090
kubectl -n finance-tracker port-forward svc/loki 3100:3100
kubectl -n finance-tracker port-forward svc/blackbox-exporter 9115:9115
kubectl -n finance-tracker port-forward svc/cadvisor 8089:8080
```

|Tool|URL|Login|
|-|-|-|
|Grafana|http://localhost:3001|admin / admin|
|Prometheus|http://localhost:9090|none|
|Blackbox Exporter|http://localhost:9115|none|
|Loki|http://localhost:3100/ready|none|
|cAdvisor|http://localhost:8089|none|

The main Grafana dashboard is automatically provisioned under:

`Dashboards -> Finance Tracker -> Finance Tracker Overview`

## What is monitored

Application health checks:

* user-service
* transaction-service
* account-service
* budget-service
* categorization-service
* goal-service
* ai-service
* banking-service
* gateway-service

Infrastructure connectivity checks:

* PostgreSQL databases
* Redis
* RabbitMQ
* Ollama

Kubernetes runtime data:

* pod CPU usage through cAdvisor
* pod memory usage through cAdvisor
* pod logs through Promtail and Loki

## Useful demo commands

```bash
kubectl get pods -n finance-tracker
kubectl get svc -n finance-tracker
kubectl get deploy,ds -n finance-tracker
kubectl logs -n finance-tracker deploy/prometheus
kubectl logs -n finance-tracker ds/promtail
```

In Prometheus, useful queries are:

```promql
probe_success{job="finance-http-health"}
probe_success{job="finance-tcp-health"}
probe_duration_seconds{job="finance-http-health"}
sum(rate(container_cpu_usage_seconds_total{container_label_io_kubernetes_pod_namespace="finance-tracker"}[1m])) by (container_label_io_kubernetes_pod_name)
```

In Grafana/Loki, useful log query:

```logql
{job="kubernetes-pods", namespace="finance-tracker"}
```

## Stop monitoring

If monitoring was deployed together with the full stack, deleting `k8s` removes it together with the application:

```bash
kubectl delete -k k8s
```

If only monitoring should be removed:

```bash
kubectl delete -k k8s/monitoring
```

## Limitations

This setup is intentionally simple. It monitors service availability, infrastructure connectivity, pod/container metrics and centralized pod logs. It does not yet include distributed tracing with OpenTelemetry, application-level custom metrics or alert delivery to email/Slack. These would be good future improvements.

cAdvisor is included as a Kubernetes DaemonSet for the local Kubernetes demo. On a managed cloud Kubernetes platform, this would usually be replaced by the platform's built-in metrics pipeline or a Helm-based Prometheus stack.
