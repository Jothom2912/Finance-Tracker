from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx
import jwt as pyjwt

logger = logging.getLogger(__name__)

API_ORIGIN = "https://api.enablebanking.com"


class EnableBankingError(Exception):
    pass


class BankConfigError(EnableBankingError):
    pass


class BankApiUnavailable(EnableBankingError):
    pass


class BankAuthorizationError(EnableBankingError):
    pass


@dataclass(frozen=True)
class EnableBankingConfig:
    app_id: str
    key_path: str
    redirect_uri: str
    # Upper bound on continuation-key pagination per account fetch —
    # protects the event loop / saga step from unbounded EB responses.
    max_tx_pages: int = 20

    def __post_init__(self) -> None:
        if not self.app_id:
            raise BankConfigError("ENABLE_BANKING_APP_ID is required")
        if self.max_tx_pages < 1:
            raise BankConfigError("max_tx_pages must be >= 1")
        path = Path(self.key_path)
        if not path.exists():
            raise BankConfigError(f"PEM key not found at {path.resolve()}")


@dataclass
class BankTransaction:
    transaction_id: str
    amount: Decimal
    currency: str
    description: str
    date: date
    creditor_name: str = ""
    debtor_name: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class EnableBankingClient:
    def __init__(self, config: EnableBankingConfig) -> None:
        self._config = config
        try:
            self._private_key = Path(config.key_path).read_bytes()
        except OSError as exc:
            raise BankConfigError(
                f"Cannot read PEM at {config.key_path}: {exc!r}"
            ) from exc
        # AsyncClient so calls from async handlers/consumers never block
        # the event loop (audit H16). One client per EnableBankingClient
        # instance: reuses the TCP/TLS connection pool across requests
        # and is closed via aclose() on process shutdown.
        self._http = httpx.AsyncClient(base_url=API_ORIGIN, timeout=30.0)
        # Smoke-test: verify PEM can actually sign a JWT at startup,
        # not at first user request after bank authorization.
        self._generate_jwt()

    async def aclose(self) -> None:
        await self._http.aclose()

    def _generate_jwt(self) -> str:
        iat = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": iat,
            "exp": iat + 3600,
        }
        try:
            return pyjwt.encode(
                payload,
                self._private_key,
                algorithm="RS256",
                headers={"kid": self._config.app_id},
            )
        except (pyjwt.PyJWTError, ValueError) as exc:
            raise BankConfigError(
                f"Failed to sign Enable Banking JWT: {exc!r}"
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._generate_jwt()}"}

    @staticmethod
    def _wrap_upstream_error(
        exc: httpx.HTTPError, context: str
    ) -> BankApiUnavailable:
        if isinstance(exc, httpx.HTTPStatusError):
            body_preview = exc.response.text[:200] if exc.response.text else ""
            return BankApiUnavailable(
                f"Enable Banking {context} returned HTTP "
                f"{exc.response.status_code}: {body_preview}"
            )
        return BankApiUnavailable(
            f"Enable Banking {context} unreachable: {exc!r}"
        )

    # ── Authorization flow ──────────────────────────────────────────

    async def get_available_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        try:
            resp = await self._http.get(
                "/aspsps",
                params={"country": country},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("aspsps", [])
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "get_available_banks") from exc

    async def start_authorization(
        self,
        bank_name: str,
        country: str = "DK",
        valid_days: int = 90,
    ) -> dict[str, str]:
        state = str(uuid.uuid4())
        body = {
            "access": {
                "valid_until": (
                    datetime.now(timezone.utc) + timedelta(days=valid_days)
                ).isoformat(),
            },
            "aspsp": {"name": bank_name, "country": country},
            "state": state,
            "redirect_url": self._config.redirect_uri,
            "psu_type": "personal",
        }
        try:
            resp = await self._http.post("/auth", json=body, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "start_authorization") from exc
        logger.info(
            "Authorization started for %s (%s), state=%s",
            bank_name,
            country,
            state,
        )
        return {"url": data["url"], "state": state}

    async def create_session(self, auth_code: str) -> dict[str, Any]:
        try:
            resp = await self._http.post(
                "/sessions",
                json={"code": auth_code},
                headers=self._headers(),
            )
            resp.raise_for_status()
            session = resp.json()
        except httpx.HTTPStatusError as exc:
            raise BankAuthorizationError(
                f"Enable Banking rejected authorization code with HTTP "
                f"{exc.response.status_code}: the code may have expired "
                f"or already been used"
            ) from exc
        except httpx.RequestError as exc:
            raise BankApiUnavailable(
                f"Enable Banking create_session unreachable: {exc!r}"
            ) from exc
        logger.info(
            "Session created: %s with %d accounts",
            session.get("session_id", "?"),
            len(session.get("accounts", [])),
        )
        return session

    async def delete_session(self, session_id: str) -> None:
        try:
            resp = await self._http.delete(
                f"/sessions/{session_id}", headers=self._headers()
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "delete_session") from exc
        logger.info("Session %s deleted", session_id)

    # ── Transaction data ────────────────────────────────────────────

    async def get_transactions(
        self,
        account_uid: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> tuple[list[BankTransaction], int]:
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc) - timedelta(days=90)
            ).date().isoformat()

        params: dict[str, str] = {"date_from": date_from}
        if date_to:
            params["date_to"] = date_to

        all_transactions: list[BankTransaction] = []
        total_skipped = 0
        continuation_key: str | None = None
        pages_fetched = 0

        while True:
            if continuation_key:
                params["continuation_key"] = continuation_key
            try:
                resp = await self._http.get(
                    f"/accounts/{account_uid}/transactions",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                raise self._wrap_upstream_error(
                    exc, "get_transactions"
                ) from exc

            batch, skipped = self._parse_batch(data.get("transactions", []))
            all_transactions.extend(batch)
            total_skipped += skipped
            pages_fetched += 1

            continuation_key = data.get("continuation_key")
            if not continuation_key:
                break
            if pages_fetched >= self._config.max_tx_pages:
                logger.warning(
                    "Transaction pagination for account %s capped at %d pages "
                    "(MAX_TX_PAGES) — upstream still returned a "
                    "continuation_key, result set is TRUNCATED "
                    "(%d transactions fetched)",
                    account_uid,
                    self._config.max_tx_pages,
                    len(all_transactions),
                )
                break

        logger.info(
            "Fetched %d transactions for account %s (skipped %d unparseable)",
            len(all_transactions),
            account_uid,
            total_skipped,
        )
        return all_transactions, total_skipped

    # ── Parsing ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_batch(
        raw_transactions: Iterable[dict[str, Any]],
    ) -> tuple[list[BankTransaction], int]:
        parsed: list[BankTransaction] = []
        skipped = 0
        for raw in raw_transactions:
            try:
                parsed.append(EnableBankingClient._parse_transaction(raw))
            except ValueError as exc:
                skipped += 1
                logger.warning(
                    "Skipping unparseable bank transaction %s: %s",
                    raw.get("entry_reference", "<unknown>"),
                    exc,
                )
        return parsed, skipped

    @staticmethod
    def _is_reference_number(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        digit_count = sum(c.isdigit() for c in stripped)
        return len(stripped) > 8 and digit_count / len(stripped) > 0.6

    @staticmethod
    def _parse_transaction(raw: dict[str, Any]) -> BankTransaction:
        amount_data = raw.get("transaction_amount", {})
        amount_str = amount_data.get("amount", "0")
        currency = amount_data.get("currency") or "DKK"

        # Decimal end-to-end (audit M19): bank amounts are exact decimal
        # strings — float would introduce binary rounding artefacts.
        try:
            amount = Decimal(str(amount_str))
        except InvalidOperation as exc:
            raise ValueError(f"Unparseable amount {amount_str!r}") from exc
        if raw.get("credit_debit_indicator") == "DBIT":
            amount = -abs(amount)

        creditor = raw.get("creditor_name", "") or (
            raw.get("creditor") or {}
        ).get("name", "")
        debtor = raw.get("debtor_name", "") or (
            raw.get("debtor") or {}
        ).get("name", "")
        human_name = creditor.strip() or debtor.strip()

        remittance_candidates = [
            raw.get("remittance_information_unstructured", ""),
            (raw.get("remittance_information_unstructured_array") or [""])[0],
            " ".join(raw.get("remittance_information") or []),
        ]
        remittance = next(
            (c.strip() for c in remittance_candidates if c and c.strip()), ""
        )

        if human_name and (
            not remittance
            or EnableBankingClient._is_reference_number(remittance)
        ):
            description = human_name
        elif remittance:
            description = remittance
        elif human_name:
            description = human_name
        else:
            description = "Ukendt"

        booking_date_raw = raw.get("booking_date") or raw.get("value_date")
        if not booking_date_raw:
            raise ValueError(
                "Bank transaction has neither booking_date nor value_date"
            )
        booking_date = date.fromisoformat(booking_date_raw)

        return BankTransaction(
            # `or`-chain, not nested .get()-defaults: EB can send the key
            # present-but-null, which a default would pass through as None.
            transaction_id=raw.get("entry_reference")
            or raw.get("transaction_id")
            or "",
            amount=amount,
            currency=currency,
            description=description,
            date=booking_date,
            creditor_name=creditor,
            debtor_name=debtor,
            status=raw.get("status", ""),
            raw=raw,
        )
