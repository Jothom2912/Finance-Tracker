"""TTL-based RuleEngine provider with startup warmup.

Preloads rule engine at startup (eliminates cold-start latency on
first request).  Reloads from DB every `ttl_seconds` so rule changes
take effect without restart.

Usage:
    provider = RuleEngineProvider(ttl_seconds=60)
    await provider.warmup()  # call once at startup

    engine = await provider.get()  # returns cached or refreshed
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.adapters.outbound.rule_engine import RuleEngine
from app.database import async_session_factory
from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from app.models import CategoryModel, SubCategoryModel

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60


class RuleEngineProvider:
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._engine: RuleEngine | None = None
        self._fallback_subcategory_id: int = 0
        self._fallback_category_id: int = 0
        self._loaded_at: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def fallback_subcategory_id(self) -> int:
        return self._fallback_subcategory_id

    @property
    def fallback_category_id(self) -> int:
        return self._fallback_category_id

    async def warmup(self) -> None:
        """Call at startup to preload engine and warm DB pool."""
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))

        await self._reload()
        logger.info("RuleEngineProvider warmup complete")

    async def get(self) -> RuleEngine:
        """Return cached engine, reloading if TTL expired."""
        now = datetime.now(timezone.utc)

        if self._engine is not None and self._loaded_at is not None:
            age = (now - self._loaded_at).total_seconds()
            if age < self._ttl:
                return self._engine

        async with self._lock:
            if self._engine is not None and self._loaded_at is not None:
                age = (now - self._loaded_at).total_seconds()
                if age < self._ttl:
                    return self._engine
            await self._reload()

        return self._engine  # type: ignore[return-value]

    async def _reload(self) -> None:
        async with async_session_factory() as session:
            cat_rows = await session.execute(select(CategoryModel))
            cats = cat_rows.scalars().all()
            cat_ids = {c.id for c in cats}

            sub_rows = await session.execute(select(SubCategoryModel))
            subs = sub_rows.scalars().all()

            subcategory_lookup: dict[str, tuple[int, int]] = {}
            for sub in subs:
                if sub.category_id in cat_ids:
                    subcategory_lookup[sub.name] = (sub.id, sub.category_id)

        keyword_mappings = [(kw, mapping["subcategory"]) for kw, mapping in SEED_MERCHANT_MAPPINGS.items()]
        self._engine = RuleEngine(
            keyword_mappings=keyword_mappings,
            subcategory_lookup=subcategory_lookup,
        )

        fallback = subcategory_lookup.get("Anden", (0, 0))
        self._fallback_subcategory_id = fallback[0]
        self._fallback_category_id = fallback[1]
        self._loaded_at = datetime.now(timezone.utc)

        logger.info(
            "RuleEngine reloaded: %d keywords, %d subcategories",
            len(keyword_mappings),
            len(subcategory_lookup),
        )
