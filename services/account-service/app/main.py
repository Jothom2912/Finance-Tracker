from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.account_api import router as account_router
from app.adapters.inbound.account_group_api import router as account_group_router
from app.config import CORS_ORIGINS

app = FastAPI(
    title="Account Service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/api/v1")
app.include_router(account_group_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "account-service"}