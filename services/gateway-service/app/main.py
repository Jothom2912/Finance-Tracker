import logging

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.graphql_api import create_graphql_router
from app.adapters.inbound.rest_api import dashboard_router
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


v1 = APIRouter(prefix="/api/v1")
v1.include_router(dashboard_router)
v1.include_router(saga_router)
v1.include_router(create_graphql_router(), prefix="/graphql")
app.include_router(v1)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8010, reload=ENVIRONMENT == "development")
