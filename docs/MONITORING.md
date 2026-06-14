# Monitoring and logging

This project includes a simple local monitoring and logging stack for Finance Tracker.

## Tools

* **Prometheus** collects metrics.
* **Blackbox Exporter** checks whether application services and infrastructure components are reachable.
* **Grafana** visualizes service health, response time, container CPU/memory and logs.
* **Loki** stores logs.
* **Promtail** collects Docker container logs and sends them to Loki.
* **cAdvisor** exposes Docker container CPU and memory metrics.

## Why this setup was chosen

The backend services already expose `/health` endpoints. To avoid risky code changes close to delivery, the monitoring stack uses Blackbox Exporter to probe these endpoints instead of adding new metrics code to every service.

This gives a useful operational overview while keeping the implementation simple:

* service up/down status
* health-check response time
* infrastructure connectivity checks
* container CPU usage
* container memory usage
* centralized container logs

## Start the monitoring stack

From the project root:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
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

## Stop the monitoring stack

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down
```

To also remove monitoring volumes:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down -v
```

## Limitations

This setup is intentionally simple. It monitors service availability, infrastructure connectivity, container metrics and logs. It does not yet include distributed tracing with OpenTelemetry, application-level custom metrics or alert delivery to email/Slack. These would be good future improvements.

