"""
Enable Banking API client.

Handles JWT generation, OAuth authorization flow, and data retrieval.
Uses httpx for HTTP requests with proper lifecycle management.

API docs: https://enablebanking.com/docs/api/reference/
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
import jwt as pyjwt

logger = logging.getLogger(__name__)

API_ORIGIN = "https://api.enablebanking.com"


@dataclass(frozen=True)
class EnableBankingConfig:
    app_id: str
    key_path: str
    redirect_uri: str
    environment: str = "sandbox"

    def __post_init__(self) -> None:
        if not self.app_id:
            raise ValueError("ENABLE_BANKING_APP_ID is required")
        path = Path(self.key_path)
        if not path.exists():
            raise FileNotFoundError(f"PEM key not found at {path.resolve()}")


@dataclass
class BankAccount:
    uid: str
    iban: str = ""
    name: str = ""
    currency: str = ""


@dataclass
class BankTransaction:
    """Raw transaction from Enable Banking API."""
    transaction_id: str
    amount: float
    currency: str
    description: str
    date: str
    creditor_name: str = ""
    debtor_name: str = ""
    status: str = ""
    raw: dict = field(default_factory=dict)


class EnableBankingClient:
    """
    Client for Enable Banking's PSD2 aggregation API.

    Lifecycle: create once at app startup, reuse across requests.
    Uses httpx.Client for connection pooling.
    """

    def __init__(self, config: EnableBankingConfig):
        self._config = config
        self._private_key = Path(config.key_path).read_bytes()
        self._http = httpx.Client(
            base_url=API_ORIGIN,
            timeout=30.0,
        )

    def close(self) -> None:
        self._http.close()

    def _generate_jwt(self) -> str:
        iat = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": iat,
            "exp": iat + 3600,
        }
        return pyjwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._config.app_id},
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._generate_jwt()}"}

    # ──────────────────────────────────────────
    # Authorization flow
    # ──────────────────────────────────────────

    def get_available_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        """List available banks (ASPSPs) for a country."""
        resp = self._http.get(
            "/aspsps", params={"country": country}, headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json().get("aspsps", [])

    def start_authorization(
        self,
        bank_name: str,
        country: str = "DK",
        valid_days: int = 90,
    ) -> dict[str, str]:
        """
        Start bank authorization flow.

        Returns dict with 'url' (redirect user here) and 'state'.
        """
        state = str(uuid.uuid4())
        body = {
            "access": {
                "valid_until": (
                    datetime.now(timezone.utc) + timedelta(days=valid_days)
                ).isoformat()
            },
            "aspsp": {"name": bank_name, "country": country},
            "state": state,
            "redirect_url": self._config.redirect_uri,
            "psu_type": "personal",
        }
        resp = self._http.post("/auth", json=body, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        logger.info("Authorization started for %s (%s), state=%s", bank_name, country, state)
        return {"url": data["url"], "state": state}

    def create_session(self, auth_code: str) -> dict[str, Any]:
        """
        Exchange authorization code for a session.

        Returns session data with session_id and list of accounts.
        """
        resp = self._http.post(
            "/sessions", json={"code": auth_code}, headers=self._headers()
        )
        resp.raise_for_status()
        session = resp.json()
        logger.info(
            "Session created: %s with %d accounts",
            session.get("session_id", "?"),
            len(session.get("accounts", [])),
        )
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get details for an existing session."""
        resp = self._http.get(
            f"/sessions/{session_id}", headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    def delete_session(self, session_id: str) -> None:
        """Revoke a session (disconnect bank)."""
        resp = self._http.delete(
            f"/sessions/{session_id}", headers=self._headers()
        )
        resp.raise_for_status()
        logger.info("Session %s deleted", session_id)

    # ──────────────────────────────────────────
    # Account data
    # ──────────────────────────────────────────

    def get_balances(self, account_uid: str) -> list[dict[str, Any]]:
        """Get balances for an account."""
        resp = self._http.get(
            f"/accounts/{account_uid}/balances", headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json().get("balances", [])

    def get_transactions(
        self,
        account_uid: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[BankTransaction]:
        """
        Fetch all transactions for an account, handling pagination.

        date_from/date_to: ISO date strings (YYYY-MM-DD).
        Defaults to last 90 days if date_from not specified.
        """
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc) - timedelta(days=90)
            ).date().isoformat()

        params: dict[str, str] = {"date_from": date_from}
        if date_to:
            params["date_to"] = date_to

        all_transactions: list[BankTransaction] = []
        continuation_key: str | None = None

        while True:
            if continuation_key:
                params["continuation_key"] = continuation_key

            resp = self._http.get(
                f"/accounts/{account_uid}/transactions",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

            for raw_txn in data.get("transactions", []):
                all_transactions.append(self._parse_transaction(raw_txn))

            continuation_key = data.get("continuation_key")
            if not continuation_key:
                break

            logger.debug(
                "Fetching more transactions (continuation_key=%s)", continuation_key
            )

        logger.info(
            "Fetched %d transactions for account %s",
            len(all_transactions), account_uid,
        )
        return all_transactions

    @staticmethod
    def _parse_transaction(raw: dict[str, Any]) -> BankTransaction:
        """Parse Enable Banking transaction response into BankTransaction."""
        amount_data = raw.get("transaction_amount", {})
        amount_str = amount_data.get("amount", "0")
        currency = amount_data.get("currency", "DKK")

        amount = float(amount_str)
        if raw.get("credit_debit_indicator") == "DBIT":
            amount = -abs(amount)

        description_candidates = [
            raw.get("remittance_information_unstructured", ""),
            (raw.get("remittance_information_unstructured_array") or [""])[0],
            " ".join(raw.get("remittance_information") or []),
            raw.get("creditor_name", ""),
            raw.get("debtor_name", ""),
            (raw.get("creditor") or {}).get("name", ""),
            (raw.get("debtor") or {}).get("name", ""),
        ]
        description = next((c.strip() for c in description_candidates if c and c.strip()), "Ukendt")

        booking_date = raw.get("booking_date", raw.get("value_date", ""))

        return BankTransaction(
            transaction_id=raw.get("entry_reference", raw.get("transaction_id", "")),
            amount=amount,
            currency=currency,
            description=description,
            date=booking_date,
            creditor_name=raw.get("creditor_name", ""),
            debtor_name=raw.get("debtor_name", ""),
            status=raw.get("status", ""),
            raw=raw,
        )
