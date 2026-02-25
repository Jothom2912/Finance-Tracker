# Presentation Outline -- Mandatory Assignment 1

Use this outline to create your PowerPoint. Each section below maps to 1-2 slides.

---

## Slide 1: Title

**Finance Tracker -- Multi-Database Personal Finance Application**

- Course: Development of Large Systems
- Repository: github.com/Jothom2912/Finance-Tracker
- Tech: FastAPI, React, MySQL, Elasticsearch, Neo4j

---

## Slide 2: Project Overview

- Personal finance tracker: transactions, budgets, goals, dashboard
- 15 functional requirements implemented
- Multi-database support (MySQL, Elasticsearch, Neo4j)
- Runtime database switching via environment variables

---

## Slide 3: System Architecture (use Mermaid diagram from report)

**Key points to highlight on this slide:**

- React frontend communicates via REST + GraphQL
- Backend organized as bounded contexts (7 domains)
- Docker Compose orchestrates all services
- Three databases with role-based selection

Paste the "High-Level System Architecture" Mermaid diagram from the report.

---

## Slide 4: Hexagonal Architecture

**Show the bounded context layout:**

```
transaction/
├── adapters/inbound/    (REST controller)
├── adapters/outbound/   (MySQL repository)
├── application/
│   ├── ports/           (interfaces)
│   └── service.py       (business logic)
└── domain/entities.py   (domain model)
```

- 7 bounded contexts follow this pattern
- Business logic isolated from infrastructure
- Prepared for microservice extraction

---

## Slide 5: CQRS Pattern

| Operation | Protocol | Example |
|-----------|----------|---------|
| Commands (write) | REST | POST /api/v1/transactions/ |
| Queries (read) | GraphQL | query { financialOverview } |

- REST handles all writes
- GraphQL serves as cross-domain read gateway
- No mutations in GraphQL -- writes always through REST
- Enables independent scaling of read/write paths

---

## Slide 6: Communication Channels

- **External:** REST + GraphQL (synchronous HTTP)
- **Internal:** Service injection via FastAPI Depends()
- **Why synchronous:** Simplicity, immediate feedback for financial data, easier debugging
- **Future:** Message broker (RabbitMQ/Kafka) for event-driven microservices

---

## Slide 7: CI/CD Pipeline

**Show the pipeline diagram from the report.**

- GitHub Actions runs on every push/PR
- Matrix testing: Python 3.11 + 3.12
- 239 tests must pass (pre-push hook + CI)
- Coverage reports to Codecov
- CD planned: Docker build, staging, manual approval, production

---

## Slide 8: Testing Strategy

```
         +----------+
         |   E2E    |   ~5% - Cypress
         +----------+
         | Integr.  |   ~19% - 45 tests
         +----------+
         |   Unit   |   ~81% - 194 tests
         +----------+
```

- 239 total tests, all passing
- Unit: mocked repos, BVA schema validation
- Integration: full HTTP stack with in-memory SQLite
- GraphQL: schema validation tests (advantage over REST)

---

## Slide 9: Deployment Strategy

- **Cloud provider:** Azure (European data residency, student credits)
- **Compute:** Azure Kubernetes Service (AKS)
- **Databases:** Azure MySQL, Elastic Cloud, Neo4j Aura
- **Monitoring:** Application Insights
- **Current:** Docker Compose for local development

---

## Slide 10: Observability

- Structured logging with correlation ID on every request
- `X-Correlation-ID` response header for end-to-end tracing
- JSON logs in production, human-readable in development
- Planned: Prometheus metrics, Grafana dashboards, alerting

---

## Slide 11: Versioning Strategy

| What | Strategy | Status |
|------|----------|--------|
| API | URL prefix: /api/v1/ | Implemented |
| Database | Alembic migrations (planned) | Designed |
| Code | Trunk-based + feature branches | Active |

- API versioning ensures backward compatibility
- Semantic commit messages
- Pre-push hooks enforce quality

---

## Slide 12: Key Takeaways

1. Hexagonal architecture enables database independence and microservice readiness
2. CQRS with REST + GraphQL separates write and read concerns
3. 239 tests with CI integration ensure quality
4. Structured logging with correlation IDs enables production debugging
5. Azure chosen for European compliance and student credits

---

## Slide 13: Demo (Live or Screenshots)

- Show the running application
- Create a transaction via REST
- Query dashboard data via GraphQL
- Show correlation ID in response headers
- Show CI pipeline running on GitHub

---

## Slide 14: Next Steps

- Frontend integration with GraphQL client
- Alembic database migrations
- Deploy to Azure AKS
- Rate limiting and security hardening
- Microservice extraction (start with transaction service)
