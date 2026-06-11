from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.application.ports.outbound import ICategoryPort
from app.auth import make_service_auth_header
from app.config import settings

logger = logging.getLogger(__name__)


class CategoryPort(ICategoryPort):
    """HTTP adapter til category-service."""

    async def exists(self, category_id: int) -> bool:
        url = f"{settings.CATEGORY_SERVICE_URL}/api/v1/categories/{category_id}"
        try:
            async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
                response = await client.get(url, headers=make_service_auth_header())
                return response.status_code == 200
        except httpx.HTTPError:
            logger.warning(
                "category_port: kunne ikke nå category-service, tillader category_id %s",
                category_id,
            )
            return True

    async def get_name(self, category_id: int) -> Optional[str]:
        url = f"{settings.CATEGORY_SERVICE_URL}/api/v1/categories/{category_id}"
        try:
            async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
                response = await client.get(url, headers=make_service_auth_header())
                if response.status_code == 200:
                    return response.json().get("name")
        except httpx.HTTPError:
            logger.warning("category_port: get_name fejlede for %s", category_id)
        return None

    async def get_all_names(self) -> dict[int, str]:
        url = f"{settings.CATEGORY_SERVICE_URL}/api/v1/categories/"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(url, headers=make_service_auth_header())
                if response.status_code == 200:
                    return {c["id"]: c["name"] for c in response.json()}
        except httpx.HTTPError:
            logger.warning("category_port: get_all_names fejlede")
        return {}
