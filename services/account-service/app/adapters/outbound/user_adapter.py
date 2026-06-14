"""Anti-corruption layer for User domain.

Implements the Account domain's IUserPort.
"""

import httpx

from app.application.ports.outbound import IUserPort
from app.config import INTERNAL_API_KEY, USER_SERVICE_URL


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

        return users
