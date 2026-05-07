from __future__ import annotations

import logging

import httpx

from app.application.ports.outbound import ICategoryPort
from app.config import settings

logger = logging.getLogger(__name__)


class CategoryPort(ICategoryPort):
    """HTTP adapter til category-service — implementerer ICategoryPort."""

    async def exists(self, category_id: int) -> bool:
        url = f"{settings.CATEGORY_SERVICE_URL}/api/v1/categories/{category_id}"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except httpx.HTTPError:
            logger.warning(
                "category_port: kunne ikke nå category-service, tillader category_id %s",
                category_id,
            )
            return True  # fail-open: blokér ikke hvis service er nede
