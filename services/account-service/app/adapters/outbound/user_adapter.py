"""Anti-corruption layer for User domain.

Implements the Account domain's IUserPort.
"""

import logging

import httpx

from app.application.ports.outbound import IUserPort
from app.config import INTERNAL_API_KEY, USER_SERVICE_URL

logger = logging.getLogger(__name__)


class UserServiceAdapter(IUserPort):
    """Anti-corruption layer for user-service."""

    def _headers(self) -> dict[str, str]:
        if not INTERNAL_API_KEY:
            return {}
        return {"X-Internal-API-Key": INTERNAL_API_KEY}

    def exists(self, user_id: int) -> bool:
        response = httpx.get(
            f"{USER_SERVICE_URL}/api/v1/users/{user_id}",
            headers=self._headers(),
            timeout=5,
        )
        # P3-59: linjen deler non-200 i to, fordi kun den ene halvdel er tvetydig.
        #
        # En 404 er user-services *entydige* måde at sige "den bruger findes ikke" på, og
        # det er præcis hvad 400'en til klienten derefter påstår.  Sandt svar, ingen linje —
        # samme fravalg som `UserNotFoundException` fik i fase 3, set fra den anden ende af
        # samme kald.
        #
        # Alt andet — 401 fordi INTERNAL_API_KEY er roteret i den ene ende, 422 fordi
        # `_headers()` udelod headeren helt, 5xx fordi user-service er syg — kollapser her til
        # det samme `False`, og klienten får "Bruger med dette ID findes ikke."  Det er en
        # konfigurations- eller driftsfejl rapporteret som en valideringsfejl, og indtil nu i
        # tavshed i begge ender.  Statuskoden er hele diskriminanten, så den står på linjen.
        #
        # Bemærk hvad linjen IKKE dækker: er user-service helt nede, kaster `httpx` en
        # `ConnectError` der ikke fanges nogen steder → 500 med uvicorns egen traceback.
        # Grimt, men ikke tavst, og at fange den her ville være den kontraktændring
        # non-goals holder ude (spawnet item 2 i planen).
        if response.status_code not in (200, 404):
            logger.warning(
                "user-service svarede %s på eksistens-tjek af bruger %s — "
                "kaldet kollapser til 'findes ikke' og bliver en 400 til klienten",
                response.status_code,
                user_id,
            )
        return response.status_code == 200

    def get_users_by_ids(self, user_ids: list[int]) -> list[tuple[int, str]]:
        users = []

        for user_id in user_ids:
            response = httpx.get(
                f"{USER_SERVICE_URL}/api/v1/users/{user_id}",
                headers=self._headers(),
                timeout=5,
            )

            if response.status_code == 200:
                user = response.json()
                user_id_value = user.get("idUser", user.get("id"))
                if user_id_value is not None:
                    users.append((int(user_id_value), user["username"]))
                else:
                    # `error`, ikke `warning`: user-service svarede 200 OK på en bruger den
                    # altså mener findes, men payloaden bar hverken `idUser` eller `id`.
                    # Det er en brudt kontrakt mellem to services vi selv ejer — vores fejl,
                    # ikke callerens — og den forsvinder i dag ud i et `InvalidUserInGroup`
                    # der ligner en almindelig tastefejl fra brugeren.
                    logger.error(
                        "user-service svarede 200 for bruger %s uden id-felt i payloaden: %s",
                        user_id,
                        sorted(user.keys()),
                    )
            elif response.status_code != 404:
                # Samme opdeling som i `exists()`: 404 er det entydige "findes ikke", alt
                # andet er en drifts- eller konfigurationsfejl der her bliver til en 400 om
                # et ugyldigt bruger-id.
                logger.warning(
                    "user-service svarede %s ved opslag af bruger %s i gruppe-validering — brugeren tælles som ugyldig",
                    response.status_code,
                    user_id,
                )

        return users
