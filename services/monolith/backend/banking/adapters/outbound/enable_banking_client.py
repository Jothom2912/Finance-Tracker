"""
Enable Banking API client.

Handles JWT generation, OAuth authorization flow, and data retrieval.
Uses httpx for HTTP requests with proper lifecycle management.

API docs: https://enablebanking.com/docs/api/reference/

Error contract
--------------
Every public method on :class:`EnableBankingClient` either returns
normally or raises one of the typed exceptions defined at the top of
this module.  The route layer (``backend/banking/presentation/rest_api``)
maps those types to HTTP status codes explicitly; anything that
escapes the typed hierarchy is a bug and propagates to FastAPI's
default 500 handler, matching the principle established for
``sync_transactions`` (see commit a6dea11 and
``docs/followups.md``).

Three adapter-level error types cover the outcomes we can classify:

* :class:`BankConfigError` — our side is misconfigured (missing
  ``app_id``, unreadable PEM, JWT signing failure).  Maps to 500.
* :class:`BankApiUnavailable` — Enable Banking is unreachable or
  returned an unexpected HTTP status.  Maps to 502.
* :class:`BankAuthorizationError` — raised *only* by
  :meth:`create_session` when Enable Banking rejects a user-supplied
  authorization code.  Maps to 400.

Call-site-based classification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``BankAuthorizationError`` is reserved for the one code path where
the user's input (``auth_code``) is the only thing that changed
between a working call and a failing one.  A rotated API key could
in principle produce an upstream 401 on ``create_session`` too, and
we would mis-classify it as a 400.  That trade-off is accepted
deliberately: a rotated key would fail ``start_authorization`` as
well (no user input involved), so the symptom is broader than
callback-only 400s.  The alternative — routing every 4xx through
``BankApiUnavailable`` — would collapse the only signal the browser
redirect loop currently has.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx
import jwt as pyjwt

logger = logging.getLogger(__name__)

API_ORIGIN = "https://api.enablebanking.com"


# ──────────────────────────────────────────────
# Typed error hierarchy
# ──────────────────────────────────────────────


class EnableBankingError(Exception):
    """Base class for typed errors originating in this adapter.

    Route handlers should pattern-match on the concrete subclasses
    (``BankConfigError``, ``BankApiUnavailable``,
    ``BankAuthorizationError``); catching ``EnableBankingError``
    directly defeats the HTTP-mapping design.  The base class exists
    only to group them for documentation and test assertions.
    """


class BankConfigError(EnableBankingError):
    """Adapter misconfiguration — missing app id, unreadable PEM, or
    a JWT that cannot be signed with the current key.

    Maps to HTTP 500.  Never the caller's fault; always an
    operational problem on our side.
    """


class BankApiUnavailable(EnableBankingError):
    """Enable Banking did not return a usable response.

    Covers network errors (``httpx.ConnectError``,
    ``httpx.TimeoutException``, any ``httpx.RequestError``) and
    unexpected HTTP statuses from upstream (``HTTPStatusError``)
    outside the authorization flow.

    Maps to HTTP 502.  The correct response to this from a caller is
    typically retry with backoff, not "check your input".
    """


class BankAuthorizationError(EnableBankingError):
    """User-supplied authorization data was rejected by Enable Banking.

    Raised exclusively from :meth:`EnableBankingClient.create_session`
    when Enable Banking returns a 4xx for the ``auth_code`` we just
    received from the browser redirect.  The typical remedy is that
    the user restarts the bank-connect flow.

    Maps to HTTP 400.  See the module docstring for the rationale
    around accepting the "rotated API key masquerading as 400" edge
    case.
    """


@dataclass(frozen=True)
class EnableBankingConfig:
    app_id: str
    key_path: str
    redirect_uri: str
    environment: str = "sandbox"

    def __post_init__(self) -> None:
        if not self.app_id:
            raise BankConfigError("ENABLE_BANKING_APP_ID is required")
        path = Path(self.key_path)
        if not path.exists():
            raise BankConfigError(f"PEM key not found at {path.resolve()}")


@dataclass
class BankAccount:
    uid: str
    iban: str = ""
    name: str = ""
    currency: str = ""


@dataclass
class BankTransaction:
    """Transaction parsed from the Enable Banking API.

    ``date`` is a domain ``date`` object; the adapter parses the bank's
    ISO-date string with ``date.fromisoformat`` before constructing this
    dataclass. Raising at the boundary keeps malformed dates local to the
    adapter instead of surfacing as obscure ``isoformat`` errors deep in
    downstream ports. See ADR-0001 on hexagonal boundaries; see
    docs/followups.md for the related date-edge-case note.
    """

    transaction_id: str
    amount: float
    currency: str
    description: str
    date: date
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
        try:
            self._private_key = Path(config.key_path).read_bytes()
        except OSError as exc:
            raise BankConfigError(f"Cannot read PEM at {config.key_path}: {exc!r}") from exc
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
        try:
            return pyjwt.encode(
                payload,
                self._private_key,
                algorithm="RS256",
                headers={"kid": self._config.app_id},
            )
        except (pyjwt.PyJWTError, ValueError) as exc:
            raise BankConfigError(f"Failed to sign Enable Banking JWT: {exc!r}") from exc

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._generate_jwt()}"}

    @staticmethod
    def _wrap_upstream_error(exc: httpx.HTTPError, context: str) -> BankApiUnavailable:
        """Translate an ``httpx`` error into ``BankApiUnavailable``.

        Handles both arms of ``httpx.HTTPError``:
          * ``HTTPStatusError`` — upstream returned a non-2xx we did not
            expect (wrapped body truncated for log hygiene).
          * ``RequestError`` — transport-level failure (connect, timeout,
            DNS, TLS).  ``httpx.ConnectError`` and
            ``httpx.TimeoutException`` are distinct subclasses that both
            land here.

        Callers that need a different mapping (e.g. ``create_session``
        treating 4xx as caller-error) must catch ``HTTPStatusError``
        first and do their own translation.
        """
        if isinstance(exc, httpx.HTTPStatusError):
            body_preview = exc.response.text[:200] if exc.response.text else ""
            return BankApiUnavailable(
                f"Enable Banking {context} returned HTTP {exc.response.status_code}: {body_preview}"
            )
        return BankApiUnavailable(f"Enable Banking {context} unreachable: {exc!r}")

    # ──────────────────────────────────────────
    # Authorization flow
    # ──────────────────────────────────────────

    def get_available_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        """List available banks (ASPSPs) for a country."""
        try:
            resp = self._http.get("/aspsps", params={"country": country}, headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("aspsps", [])
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "get_available_banks") from exc

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
            "access": {"valid_until": (datetime.now(timezone.utc) + timedelta(days=valid_days)).isoformat()},
            "aspsp": {"name": bank_name, "country": country},
            "state": state,
            "redirect_url": self._config.redirect_uri,
            "psu_type": "personal",
        }
        try:
            resp = self._http.post("/auth", json=body, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "start_authorization") from exc
        logger.info("Authorization started for %s (%s), state=%s", bank_name, country, state)
        return {"url": data["url"], "state": state}

    def create_session(self, auth_code: str) -> dict[str, Any]:
        """
        Exchange authorization code for a session.

        Returns session data with session_id and list of accounts.

        Error contract: this is the only method that maps upstream 4xx
        responses to ``BankAuthorizationError`` (HTTP 400) rather than
        ``BankApiUnavailable`` (HTTP 502).  The ``auth_code`` is supplied
        by the caller after a browser redirect from the bank and is
        almost always the variable being rejected — expired,
        already-used, or tampered.  Rotated-API-key edge cases are
        documented in the module docstring.
        """
        try:
            resp = self._http.post("/sessions", json={"code": auth_code}, headers=self._headers())
            resp.raise_for_status()
            session = resp.json()
        except httpx.HTTPStatusError as exc:
            raise BankAuthorizationError(
                f"Enable Banking rejected authorization code with HTTP "
                f"{exc.response.status_code}: the code may have expired or already been used"
            ) from exc
        except httpx.RequestError as exc:
            raise BankApiUnavailable(f"Enable Banking create_session unreachable: {exc!r}") from exc
        logger.info(
            "Session created: %s with %d accounts",
            session.get("session_id", "?"),
            len(session.get("accounts", [])),
        )
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get details for an existing session."""
        try:
            resp = self._http.get(f"/sessions/{session_id}", headers=self._headers())
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "get_session") from exc

    def delete_session(self, session_id: str) -> None:
        """Revoke a session (disconnect bank)."""
        try:
            resp = self._http.delete(f"/sessions/{session_id}", headers=self._headers())
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "delete_session") from exc
        logger.info("Session %s deleted", session_id)

    # ──────────────────────────────────────────
    # Account data
    # ──────────────────────────────────────────

    def get_balances(self, account_uid: str) -> list[dict[str, Any]]:
        """Get balances for an account."""
        try:
            resp = self._http.get(f"/accounts/{account_uid}/balances", headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("balances", [])
        except httpx.HTTPError as exc:
            raise self._wrap_upstream_error(exc, "get_balances") from exc

    def get_transactions(
        self,
        account_uid: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> tuple[list[BankTransaction], int]:
        """
        Fetch all transactions for an account, handling pagination.

        date_from/date_to: ISO date strings (YYYY-MM-DD).
        Defaults to last 90 days if date_from not specified.

        Returns ``(transactions, parse_skipped)``.  ``parse_skipped`` is
        the aggregate count of transactions the adapter dropped because
        their payload could not be parsed (see ``_parse_batch``).
        Surfacing the count lets the sync endpoint report it to the
        caller instead of burying it in a WARNING log — a silent sync
        that skipped 40 of 200 transactions is a failure the user
        deserves to see.
        """
        if date_from is None:
            date_from = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()

        params: dict[str, str] = {"date_from": date_from}
        if date_to:
            params["date_to"] = date_to

        all_transactions: list[BankTransaction] = []
        total_skipped = 0
        continuation_key: str | None = None

        while True:
            if continuation_key:
                params["continuation_key"] = continuation_key

            try:
                resp = self._http.get(
                    f"/accounts/{account_uid}/transactions",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                raise self._wrap_upstream_error(exc, "get_transactions") from exc

            batch, skipped = self._parse_batch(data.get("transactions", []))
            all_transactions.extend(batch)
            total_skipped += skipped

            continuation_key = data.get("continuation_key")
            if not continuation_key:
                break

            logger.debug("Fetching more transactions (continuation_key=%s)", continuation_key)

        logger.info(
            "Fetched %d transactions for account %s (skipped %d unparseable)",
            len(all_transactions),
            account_uid,
            total_skipped,
        )
        return all_transactions, total_skipped

    @staticmethod
    def _parse_batch(
        raw_transactions: Iterable[dict[str, Any]],
    ) -> tuple[list[BankTransaction], int]:
        """Parse a list of raw bank transactions, skipping unparseable ones.

        Isolates per-transaction parse failures so a single malformed
        payload from the bank does not abort the whole paginated batch.
        Each skip is logged at WARNING level with the transaction's
        entry_reference for operational traceability; callers log the
        aggregate skip count once pagination is complete.

        Returns a tuple of (successfully_parsed, skipped_count).
        """
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
        """Check if text looks like a bank reference number rather than a name."""
        stripped = text.strip()
        if not stripped:
            return True
        digit_count = sum(c.isdigit() for c in stripped)
        return len(stripped) > 8 and digit_count / len(stripped) > 0.6

    @staticmethod
    def _parse_transaction(raw: dict[str, Any]) -> BankTransaction:
        """Parse Enable Banking transaction response into BankTransaction."""
        amount_data = raw.get("transaction_amount", {})
        amount_str = amount_data.get("amount", "0")
        currency = amount_data.get("currency", "DKK")

        amount = float(amount_str)
        if raw.get("credit_debit_indicator") == "DBIT":
            amount = -abs(amount)

        creditor = raw.get("creditor_name", "") or (raw.get("creditor") or {}).get("name", "")
        debtor = raw.get("debtor_name", "") or (raw.get("debtor") or {}).get("name", "")
        human_name = creditor.strip() or debtor.strip()

        remittance_candidates = [
            raw.get("remittance_information_unstructured", ""),
            (raw.get("remittance_information_unstructured_array") or [""])[0],
            " ".join(raw.get("remittance_information") or []),
        ]
        remittance = next((c.strip() for c in remittance_candidates if c and c.strip()), "")

        if human_name and (not remittance or EnableBankingClient._is_reference_number(remittance)):
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
                "Bank transaction has neither booking_date nor value_date; cannot determine transaction date",
            )
        booking_date = date.fromisoformat(booking_date_raw)

        return BankTransaction(
            transaction_id=raw.get("entry_reference", raw.get("transaction_id", "")),
            amount=amount,
            currency=currency,
            description=description,
            date=booking_date,
            creditor_name=creditor,
            debtor_name=debtor,
            status=raw.get("status", ""),
            raw=raw,
        )
