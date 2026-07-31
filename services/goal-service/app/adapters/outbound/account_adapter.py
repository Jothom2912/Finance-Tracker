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

    async def exists(self, account_id: int) -> bool:
        """Findes kontoen?

        P3-59: de to metoder håndterer de samme fejl på modsat vis.  ``get_owner_user_id``
        nedenfor oversætter upstream-problemer til ``UpstreamServiceUnavailable`` → 503,
        hvilket er ærligt.  ``exists`` kollapser alt til ``False``, hvilket ville blive en
        400 "Account N not found" — en besked klienten med rette aldrig genforsøger.

        **Men det sker ikke, og det er værd at skrive ned.**  Eneste kalder er
        ``service.py:94`` i ``create_goal``, og den kalder ``_verify_ownership`` to linjer
        tidligere (``:92``) — altså ``get_owner_user_id`` mod *samme* upstream.  Er
        account-service nede eller nøglen skæv, rejses 503'en dér.  Live-drevet i to
        fejlmoder (skæv ``INTERNAL_API_KEY``, ikke-eksisterende host): ``POST /goals``
        giver 503, ikke 400, og de to linjer nedenfor fyrede aldrig.  De to fejlgrene her
        er altså **uopnåelige fra en request** — dækket af adapter-tests, men ikke talt
        som HTTP-drevne linjer.

        Cuttet er stadig simplere end i account-services ``user_adapter``, og med vilje:
        ``/exists`` svarer ``200 {"exists": false}`` når kontoen ikke findes, så den har
        ingen 404-gren.  Enhver non-200 herfra ville derfor være anomal.

        Selve redundansen — to round-trips hvor den første allerede 404'er hvis kontoen
        ikke findes — er en adfærdsændring og hører i et eget item, ikke her (non-goal).
        """
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/internal/accounts/{account_id}/exists",
                    headers=headers,
                )
            if response.status_code != 200:
                logger.warning(
                    "account-service svarede %s på eksistens-tjek af konto %s — "
                    "kaldet kollapser til 'findes ikke' og bliver en 400 til klienten",
                    response.status_code,
                    account_id,
                )
                return False
            return response.json().get("exists") is True
        except httpx.RequestError as exc:
            logger.warning(
                "account-service kunne ikke nås ved eksistens-tjek af konto %s (%s: %s) — "
                "kaldet kollapser til 'findes ikke' og bliver en 400 til klienten",
                account_id,
                type(exc).__name__,
                exc,
            )
            return False

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
