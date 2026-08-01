"""Anti-corruption layer for User domain.

Implements the Account domain's IUserPort.
"""

import logging

import httpx

from app.application.ports.outbound import IUserPort
from app.config import INTERNAL_API_KEY, USER_SERVICE_URL
from app.domain.exceptions import UpstreamServiceUnavailable

logger = logging.getLogger(__name__)


class UserServiceAdapter(IUserPort):
    """Anti-corruption layer for user-service."""

    def _headers(self) -> dict[str, str]:
        if not INTERNAL_API_KEY:
            return {}
        return {"X-Internal-API-Key": INTERNAL_API_KEY}

    def exists(self, user_id: int) -> bool:
        try:
            response = httpx.get(
                f"{USER_SERVICE_URL}/api/v1/users/{user_id}",
                headers=self._headers(),
                timeout=5,
            )
        except httpx.RequestError as exc:
            logger.warning(
                "user-service kunne ikke nås ved eksistens-tjek af bruger %s (%s: %s)",
                user_id,
                type(exc).__name__,
                exc,
            )
            raise UpstreamServiceUnavailable("user-service") from exc

        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False

        logger.warning(
            "user-service svarede %s på eksistens-tjek af bruger %s — behandles som utilgængelig",
            response.status_code,
            user_id,
        )
        raise UpstreamServiceUnavailable("user-service")

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
