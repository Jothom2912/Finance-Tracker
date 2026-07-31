import logging

import uvicorn
from fastapi import FastAPI
from observability import setup_logging

from app.adapters.inbound.graphql_api import create_graphql_router
from app.adapters.inbound.saga_api import saga_router
from app.config import ENVIRONMENT, LOG_LEVEL

# P3-57: var husets eneste fungerende logging-konfiguration og dermed før-målingens
# kontrol. Erstattet af den delte, som også overtager uvicorns tre loggere — dens format
# er workernes (millisekunder i asctime), ikke basicConfig-blokkens.
setup_logging(LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(title="Gateway Service")


@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway-service"}


app.include_router(saga_router, prefix="/api/v1")
app.include_router(create_graphql_router(), prefix="/api/v1/graphql")

if __name__ == "__main__":
    # Bind-all is intentional: the containerized service must listen on
    # 0.0.0.0 for Docker port mapping to work (mirrors the Dockerfile CMD).
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # nosec B104
        port=8010,
        reload=ENVIRONMENT == "development",
    )
