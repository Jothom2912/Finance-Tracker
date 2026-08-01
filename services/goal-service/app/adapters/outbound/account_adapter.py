from __future__ import annotations

import logging

import httpx
from app.domain.exceptions import AccountNotFoundForGoal, UpstreamServiceUnavailable

logger = logging.getLogger(__name__)


class AccountServiceAdapter:
    """Adapter for verifying account existence via account-service."""

    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def get_owner_user_id(self, account_id: int) -> int:
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/internal/accounts/{account_id}/owner",
                    headers=headers,
                )
        except httpx.RequestError as exc:
            # P3-59: 503'en er ærlig udad, men bærer kun "account-service is unavailable".
            # Diskriminanten — timeout vs. connect-fejl vs. afbrudt læsning — findes kun her.
            logger.warning(
                "account-service kunne ikke nås ved ejerskabs-opslag på konto %s (%s: %s)",
                account_id,
                type(exc).__name__,
                exc,
            )
            raise UpstreamServiceUnavailable("account-service") from exc
        if response.status_code == 404:
            # Fravalg: entydigt.  Kontoen findes ikke, og 400'en siger præcis det med
            # konto-id'et på.  Det er samtidig helt normal brug (forældet id i frontenden).
            raise AccountNotFoundForGoal(account_id)
        if response.status_code == 200:
            return int(response.json()["user_id"])
        # Samme 503, en helt anden årsag: account-service SVAREDE, bare ikke noget vi kan
        # bruge — typisk 403 fordi den interne nøgle er roteret i den ene ende.  Uden
        # statuskoden er den umulig at skelne fra nedetid ovenfor.
        logger.warning(
            "account-service svarede %s på ejerskabs-opslag af konto %s — behandles som utilgængelig",
            response.status_code,
            account_id,
        )
        raise UpstreamServiceUnavailable("account-service")
