"""P2-40: ``get_account_id_from_headers`` må aldrig returnere en konto brugeren ikke har valgt.

Gateway'en havde indtil P2-40 **ingen** test af ``auth.py``, og det er grunden til at
``accounts[0]``-fallbacken kunne leve: browser-suiten seeder én konto pr. bruger, og med én
konto er ``accounts[0]`` altid det rigtige svar. Testen der bærer fixet er ``test_no_header_
picks_default_account_not_first_in_list`` — den er den eneste her der er rød med
``accounts[0]``.

Account-service mockes gennem ``httpx.MockTransport``, ikke en bar ``MagicMock``: fixet læser
``resp.status_code`` og ``resp.json()`` på et rigtigt ``httpx.Response``, og en MagicMock ville
svare truthy på hvad som helst — jf. P3-41.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import httpx
import pytest
from app import auth
from jose import jwt

USER_ID = 4711
FOREIGN_ACCOUNT_ID = 99


def _token(user_id: int = USER_ID) -> str:
    """Et gyldigt gateway-token. ``exp`` er obligatorisk siden P1-15 (``require_exp``)."""
    return jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth.SECRET_KEY,
        algorithm=auth.JWT_ALGORITHM,
    )


def _account(account_id: int, name: str) -> dict[str, Any]:
    """Account-services svarform: nøglen er ``idAccount``, ikke ``id``."""
    return {"idAccount": account_id, "name": name, "saldo": 0.0}


@pytest.fixture
def mock_account_service(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], list[str]]:
    """Rut ``auth.httpx.get`` gennem en ``MockTransport`` og opsaml de kaldte URL'er.

    Returnerer listen over URL'er, så testene kan sige noget om *hvilket* endpoint
    fallbacken rammer — den trailing slash er dyrt købt (307'eren i
    findings/2026-07-27-gateway-default-account-307).
    """

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> list[str]:
        called: list[str] = []

        def fake_get(url: str, **kwargs: Any) -> httpx.Response:
            called.append(url)
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                return client.get(url, **kwargs)

        monkeypatch.setattr(auth.httpx, "get", fake_get)
        return called

    return install


# ── (a) header sendt + ejerskab ok ──────────────────────────────────


def test_header_with_owned_account_returns_that_id(mock_account_service: Any) -> None:
    called = mock_account_service(lambda request: httpx.Response(200, json=_account(7, "Whatever")))

    assert auth.get_account_id_from_headers(f"Bearer {_token()}", "7") == 7
    assert called == [f"{auth.ACCOUNT_SERVICE_URL}/api/v1/accounts/7"]


# ── (b) header sendt + fremmed konto ────────────────────────────────


def test_header_with_foreign_account_returns_none(mock_account_service: Any) -> None:
    """Ejerskabs-checket ligger i account-services 404/403, ikke i gateway'en."""
    mock_account_service(lambda request: httpx.Response(404, json={"detail": "Not found"}))

    assert auth.get_account_id_from_headers(f"Bearer {_token()}", str(FOREIGN_ACCOUNT_ID)) is None


# ── (c) DEN test der bærer fixet ────────────────────────────────────


def test_no_header_picks_default_account_not_first_in_list(mock_account_service: Any) -> None:
    """'Default Account' står SIDST i svaret — og skal stadig vælges.

    Rækkefølgen her er ikke opdigtet: account-services ``get_all`` har ingen ``ORDER BY``, og
    opstillingen blev målt live på compose-stakken (bruger 428, konti 432/433), hvor
    fallbacken returnerede den forkerte kontos 1554,00 kr. uden en fejl.

    Denne test er rød hvis ``accounts[0]`` genindføres — det er hele dens formål.
    """
    accounts = [_account(432, "Gammel Konto"), _account(433, "Default Account")]
    called = mock_account_service(lambda request: httpx.Response(200, json=accounts))

    assert auth.get_account_id_from_headers(f"Bearer {_token()}", None) == 433
    # Trailing slash: uden den svarer account-service 307, som httpx ikke følger.
    assert called == [f"{auth.ACCOUNT_SERVICE_URL}/api/v1/accounts/"]


# ── (d) ingen defaultkonto → ærlig fejl frem for gæt ────────────────


def test_no_header_and_no_default_account_returns_none(
    mock_account_service: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Brugeren mister fallbacken helt, og det logges med ``user_id`` (P2-40's risiko-note)."""
    accounts = [_account(432, "Gammel Konto"), _account(434, "Feriekonto")]
    mock_account_service(lambda request: httpx.Response(200, json=accounts))

    with caplog.at_level("WARNING", logger=auth.logger.name):
        assert auth.get_account_id_from_headers(f"Bearer {_token()}", None) is None

    assert str(USER_ID) in caplog.text


# ── (e) tom liste ───────────────────────────────────────────────────


def test_no_header_and_no_accounts_returns_none(mock_account_service: Any) -> None:
    mock_account_service(lambda request: httpx.Response(200, json=[]))

    assert auth.get_account_id_from_headers(f"Bearer {_token()}", None) is None
