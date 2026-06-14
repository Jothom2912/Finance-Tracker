from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    bank_name: str
    country: str = "DK"
    account_id: int = Field(gt=0)


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str


class SyncRequest(BaseModel):
    date_from: Optional[str] = None


class ConnectionResponse(BaseModel):
    id: UUID
    bank_name: str
    bank_country: str
    iban: Optional[str]
    status: str
    last_synced_at: Optional[str]
    created_at: Optional[str]
