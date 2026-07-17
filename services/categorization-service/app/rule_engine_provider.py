"""TTL-based RuleEngine provider with startup warmup and per-user overlays.

Preloads the global rule engine at startup (eliminates cold-start
latency on first request) and reloads from DB every `ttl_seconds` so
rule changes take effect without restart.

F1-02: `get(user_id=...)` returns a TieredRuleEngine that tries the
user's own rules first (grouped by priority ascending — learned
corrections at 10 beat user-created at 50; longest-match within a
group) and falls through to the shared global engine.  User overlays
are cached per user with the same TTL; `invalidate_user()` lets the
API process apply rule mutations instantly (worker processes converge
via TTL).

Usage:
    provider = RuleEngineProvider(ttl_seconds=60)
    await provider.warmup()  # call once at startup

    engine = await provider.get()            # global rules only
    engine = await provider.get(user_id=7)   # user overlay + global
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from itertools import groupby

from sqlalchemy import select, text

from app.adapters.outbound.postgres_rule_repository import PostgresRuleRepository
from app.adapters.outbound.rule_engine import RuleEngine, TieredRuleEngine
from app.database import async_session_factory
from app.domain.value_objects import PatternType
from app.models import CategoryModel, SubCategoryModel

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60
# Both user-authored keywords and learned merchant patterns are plain
# contains-matches to the engine; REGEX/AMOUNT_RANGE stay unimplemented.
_MATCHABLE_PATTERN_TYPES = (PatternType.KEYWORD, PatternType.MERCHANT)
_MAX_USER_CACHE = 512


class RuleEngineProvider:
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._engine: RuleEngine | None = None
        self._fallback_subcategory_id: int = 0
        self._fallback_category_id: int = 0
        self._loaded_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._subcategory_lookup: dict[str, tuple[int, int]] = {}
        self._subcategory_name_by_id: dict[int, str] = {}
        self._user_engines: dict[int, tuple[list[RuleEngine], datetime]] = {}

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

    async def get(self, user_id: int | None = None):  # noqa: ANN201 — IRuleEngine protocol
        """Return the cached engine (reloading if TTL expired).

        With a user_id, the user's own active rules are layered ON TOP
        of the global engine; without one, behavior is identical to the
        pre-F1-02 provider (zero-rules users share that guarantee).
        """
        global_engine = await self._get_global()
        if user_id is None:
            return global_engine

        user_engines = await self._get_user_engines(user_id)
        if not user_engines:
            return global_engine
        return TieredRuleEngine([*user_engines, global_engine])

    def invalidate_user(self, user_id: int) -> None:
        """Drop a user's cached overlay so the next categorize rebuilds it."""
        self._user_engines.pop(user_id, None)

    async def _get_global(self) -> RuleEngine:
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

    async def _get_user_engines(self, user_id: int) -> list[RuleEngine]:
        now = datetime.now(timezone.utc)
        cached = self._user_engines.get(user_id)
        if cached is not None and (now - cached[1]).total_seconds() < self._ttl:
            return cached[0]

        async with self._lock:
            cached = self._user_engines.get(user_id)
            if cached is not None and (now - cached[1]).total_seconds() < self._ttl:
                return cached[0]

            engines = await self._load_user_engines(user_id)
            if len(self._user_engines) >= _MAX_USER_CACHE:
                oldest = min(self._user_engines, key=lambda uid: self._user_engines[uid][1])
                del self._user_engines[oldest]
            self._user_engines[user_id] = (engines, datetime.now(timezone.utc))
            return engines

    async def _load_user_engines(self, user_id: int) -> list[RuleEngine]:
        """One RuleEngine per priority group, ascending — tier order is
        the priority ladder (10 learned < 50 user < seeds in global)."""
        async with async_session_factory() as session:
            rules = await PostgresRuleRepository(session).find_by_user(user_id)

        matchable = [
            rule
            for rule in rules
            if rule.active
            and rule.pattern_type in _MATCHABLE_PATTERN_TYPES
            and rule.matches_subcategory_id in self._subcategory_name_by_id
        ]

        engines: list[RuleEngine] = []
        for _prio, group in groupby(matchable, key=lambda r: r.priority):
            mappings = [(r.pattern_value, self._subcategory_name_by_id[r.matches_subcategory_id]) for r in group]
            engines.append(RuleEngine(keyword_mappings=mappings, subcategory_lookup=self._subcategory_lookup))

        if engines:
            logger.debug("Built %d user rule tier(s) for user %d", len(engines), user_id)
        return engines

    async def _reload(self) -> None:
        async with async_session_factory() as session:
            cat_rows = await session.execute(select(CategoryModel))
            cats = cat_rows.scalars().all()
            cat_ids = {c.id for c in cats}

            sub_rows = await session.execute(select(SubCategoryModel))
            subs = sub_rows.scalars().all()

            subcategory_lookup: dict[str, tuple[int, int]] = {}
            subcategory_name_by_id: dict[int, str] = {}
            for sub in subs:
                subcategory_name_by_id[sub.id] = sub.name
                if sub.category_id in cat_ids:
                    subcategory_lookup[sub.name] = (sub.id, sub.category_id)

            rules = await PostgresRuleRepository(session).find_active_rules()

        keyword_mappings = [
            (rule.pattern_value, subcategory_name_by_id[rule.matches_subcategory_id])
            for rule in rules
            if rule.pattern_type == PatternType.KEYWORD and rule.matches_subcategory_id in subcategory_name_by_id
        ]
        self._engine = RuleEngine(
            keyword_mappings=keyword_mappings,
            subcategory_lookup=subcategory_lookup,
        )
        self._subcategory_lookup = subcategory_lookup
        self._subcategory_name_by_id = subcategory_name_by_id
        # Taxonomy maps changed — cached user overlays reference the old
        # lookup, so rebuild them lazily on next use.
        self._user_engines.clear()

        fallback = subcategory_lookup.get("Anden", (0, 0))
        self._fallback_subcategory_id = fallback[0]
        self._fallback_category_id = fallback[1]
        self._loaded_at = datetime.now(timezone.utc)

        logger.info(
            "RuleEngine reloaded: %d keywords, %d subcategories",
            len(keyword_mappings),
            len(subcategory_lookup),
        )


# Module-level singleton — imported by both app.main (startup warmup) and
# app.dependencies (request-time DI) so neither has to reach into the other
# and risk a circular import.
rule_engine_provider = RuleEngineProvider(ttl_seconds=DEFAULT_TTL_SECONDS)
