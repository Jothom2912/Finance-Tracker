import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.graphql_api import create_graphql_router
from app.adapters.inbound.saga_api import saga_router
from app.config import CORS_ORIGINS, ENVIRONMENT, LOG_LEVEL

_log_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Gateway Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway-service"}


app.include_router(saga_router, prefix="/api/v1")
app.include_router(create_graphql_router(), prefix="/api/v1/graphql")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8010, reload=ENVIRONMENT == "development")
