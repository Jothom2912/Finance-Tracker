# Analytics Service (Planned)

**Status: Stub.** Analytics and the GraphQL read gateway are handled by gateway-service on port 8010.

This service is reserved for future Elasticsearch-backed denormalized read views and reporting. Currently only exposes a health endpoint.

## Current Alternative

Analytics/dashboard reads are served by:
- `services/gateway-service/` — REST dashboard + GraphQL on port 8010
