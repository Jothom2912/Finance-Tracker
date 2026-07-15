from __future__ import annotations

import json
import logging
from decimal import Decimal

import httpx
import pytest
from app.adapters.outbound.enable_banking_client import (
    BankConfigError,
    EnableBankingClient,
    EnableBankingConfig,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture(scope="module")
def pem_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Real RSA key so the client's startup JWT smoke-test passes."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path = tmp_path_factory.mktemp("keys") / "eb.pem"
    path.write_bytes(pem)
    return str(path)


def make_client(pem_path: str, handler, max_tx_pages: int = 20) -> EnableBankingClient:
    config = EnableBankingConfig(
        app_id="test-app",
        key_path=pem_path,
        redirect_uri="http://localhost/callback",
        max_tx_pages=max_tx_pages,
    )
    client = EnableBankingClient(config)
    # Swap the transport so no real network I/O happens; the client's
    # own AsyncClient (and its base_url/headers handling) stays in play.
    client._http._transport = httpx.MockTransport(handler)
    return client


# ── Decimal parsing (M19) ───────────────────────────────────────────


def test_parse_transaction_amount_is_exact_decimal() -> None:
    txn = EnableBankingClient._parse_transaction(
        {
            "transaction_amount": {"amount": "123.45", "currency": "DKK"},
            "credit_debit_indicator": "CRDT",
            "booking_date": "2026-07-01",
        }
    )

    assert isinstance(txn.amount, Decimal)
    assert txn.amount == Decimal("123.45")
    assert txn.currency == "DKK"


def test_parse_transaction_debit_is_negative_decimal() -> None:
    txn = EnableBankingClient._parse_transaction(
        {
            "transaction_amount": {"amount": "0.10", "currency": "DKK"},
            "credit_debit_indicator": "DBIT",
            "booking_date": "2026-07-01",
        }
    )

    assert txn.amount == Decimal("-0.10")


def test_parse_batch_skips_unparseable_amount() -> None:
    parsed, skipped = EnableBankingClient._parse_batch(
        [
            {
                "transaction_amount": {"amount": "not-a-number"},
                "booking_date": "2026-07-01",
            },
            {
                "transaction_amount": {"amount": "10.00"},
                "booking_date": "2026-07-01",
            },
        ]
    )

    assert skipped == 1
    assert len(parsed) == 1
    assert parsed[0].amount == Decimal("10.00")


# ── Async pagination + page cap (H16) ───────────────────────────────


def _tx(amount: str = "10.00") -> dict:
    return {
        "transaction_amount": {"amount": amount, "currency": "DKK"},
        "booking_date": "2026-07-01",
        "credit_debit_indicator": "CRDT",
    }


@pytest.mark.asyncio
async def test_get_transactions_follows_continuation_keys(pem_path: str) -> None:
    pages = [
        {"transactions": [_tx("1.00"), _tx("2.00")], "continuation_key": "next-1"},
        {"transactions": [_tx("3.00")], "continuation_key": None},
    ]
    calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params.get("continuation_key"))
        return httpx.Response(200, json=pages[len(calls) - 1])

    client = make_client(pem_path, handler)
    try:
        transactions, skipped = await client.get_transactions("acc-uid")
    finally:
        await client.aclose()

    assert len(transactions) == 3
    assert skipped == 0
    assert calls == [None, "next-1"]
    assert all(isinstance(t.amount, Decimal) for t in transactions)


@pytest.mark.asyncio
async def test_get_transactions_caps_pages_and_warns(pem_path: str, caplog: pytest.LogCaptureFixture) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        # Upstream always claims there is another page.
        return httpx.Response(
            200,
            json={"transactions": [_tx()], "continuation_key": f"next-{call_count}"},
        )

    client = make_client(pem_path, handler, max_tx_pages=3)
    with caplog.at_level(logging.WARNING):
        try:
            transactions, _ = await client.get_transactions("acc-uid")
        finally:
            await client.aclose()

    assert call_count == 3
    assert len(transactions) == 3
    truncation_warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "TRUNCATED" in r.getMessage()]
    assert len(truncation_warnings) == 1


@pytest.mark.asyncio
async def test_get_transactions_serializes_decimal_amount_as_string(pem_path: str) -> None:
    """Guard the saga contract: str(Decimal) must stay a plain decimal string."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"transactions": [_tx("1234.56")], "continuation_key": None})

    client = make_client(pem_path, handler)
    try:
        transactions, _ = await client.get_transactions("acc-uid")
    finally:
        await client.aclose()

    # Same serialization the saga consumer uses for the import payload.
    assert str(abs(transactions[0].amount)) == "1234.56"
    assert json.dumps({"amount": str(abs(transactions[0].amount))})


def test_config_rejects_non_positive_page_cap(pem_path: str) -> None:
    with pytest.raises(BankConfigError):
        EnableBankingConfig(
            app_id="test-app",
            key_path=pem_path,
            redirect_uri="http://localhost/callback",
            max_tx_pages=0,
        )
