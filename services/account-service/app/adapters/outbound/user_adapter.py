"""Anti-corruption layer for User domain.

Implements the Account domain's IUserPort.
"""

import httpx

from app.application.ports.outbound import IUserPort
from app.config import USER_SERVICE_URL


class UserServiceAdapter(IUserPort):
    """Anti-corruption layer for user-service."""

    def exists(self, user_id: int) -> bool:
        response = httpx.get(f"{USER_SERVICE_URL}/api/v1/users/{user_id}", timeout=5)
        return response.status_code == 200

    def get_users_by_ids(self, user_ids: list[int]) -> list[tuple[int, str]]:
        users = []

        for user_id in user_ids:
            response = httpx.get(f"{USER_SERVICE_URL}/api/v1/users/{user_id}", timeout=5)

            if response.status_code == 200:
                user = response.json()
                users.append((user["idUser"], user["username"]))

        return users