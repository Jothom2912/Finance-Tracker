from fastapi import FastAPI
from observability import setup_logging

from app.adapters.inbound.account_api import router as account_router
from app.adapters.inbound.account_group_api import router as account_group_router
from app.adapters.inbound.internal_api import router as internal_router
from app.config import LOG_LEVEL

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging(LOG_LEVEL)

app = FastAPI(title="Account Service", version="0.1.0")


app.include_router(account_router, prefix="/api/v1")
app.include_router(account_group_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "account-service"}
