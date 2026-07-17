"""Unit tests for the provider's per-user overlay (F1-02).

The global engine + taxonomy maps are injected directly (the global
reload path is exercised live and by integration tests); the user-rule
DB fetch is faked at the repository seam.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.adapters.outbound.rule_engine import RuleEngine
from app.domain.entities import CategorizationRule
from app.domain.value_objects import PatternType
from app.rule_engine_provider import RuleEngineProvider

LOOKUP = {
    "Dagligvarer": (1, 1),
    "Restaurant": (2, 1),
    "Kiosk": (3, 1),
    "Anden": (99, 8),
}
NAME_BY_ID = {1: "Dagligvarer", 2: "Restaurant", 3: "Kiosk", 99: "Anden"}


def _rule(**overrides: object) -> CategorizationRule:
    defaults: dict = {
        "id": 1,
        "user_id": 7,
        "priority": 50,
        "pattern_type": PatternType.KEYWORD,
        "pattern_value": "netto",
        "matches_subcategory_id": 2,
        "active": True,
    }
    defaults.update(overrides)
    return CategorizationRule(**defaults)


def _provider(global_keywords: list[tuple[str, str]]) -> RuleEngineProvider:
    provider = RuleEngineProvider(ttl_seconds=3600)
    provider._engine = RuleEngine(global_keywords, LOOKUP)
    provider._loaded_at = datetime.now(timezone.utc)
    provider._subcategory_lookup = LOOKUP
    provider._subcategory_name_by_id = NAME_BY_ID
    return provider


def _patch_user_rules(rules: list[CategorizationRule]) -> tuple[object, MagicMock]:
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    repo = MagicMock()
    repo.return_value.find_by_user = AsyncMock(return_value=rules)
    return (
        patch.multiple(
            "app.rule_engine_provider",
            async_session_factory=session_factory,
            PostgresRuleRepository=repo,
        ),
        repo,
    )


class TestUserOverlay:
    @pytest.mark.asyncio()
    async def test_user_rule_beats_longer_global_keyword(self) -> None:
        provider = _provider([("netto vesterbro", "Dagligvarer")])
        ctx, _ = _patch_user_rules([_rule(pattern_value="netto", matches_subcategory_id=2)])

        with ctx:
            engine = await provider.get(user_id=7)

        result = engine.match("Netto Vesterbro", -100.0)
        assert result is not None
        assert result.subcategory_id == 2  # user's Restaurant rule won

    @pytest.mark.asyncio()
    async def test_zero_rules_user_gets_the_global_engine_itself(self) -> None:
        """Identity, not just equivalence — the pre-F1-02 path must be
        byte-identical for users without rules."""
        provider = _provider([("netto", "Dagligvarer")])
        ctx, _ = _patch_user_rules([])

        with ctx:
            engine = await provider.get(user_id=7)

        assert engine is provider._engine

    @pytest.mark.asyncio()
    async def test_no_user_id_returns_global_engine(self) -> None:
        provider = _provider([("netto", "Dagligvarer")])

        assert (await provider.get()) is provider._engine

    @pytest.mark.asyncio()
    async def test_learned_priority_10_beats_user_priority_50(self) -> None:
        provider = _provider([])
        ctx, _ = _patch_user_rules(
            [
                # find_by_user returns priority-ascending order (repo contract)
                _rule(
                    id=2,
                    priority=10,
                    pattern_type=PatternType.MERCHANT,
                    pattern_value="netto",
                    matches_subcategory_id=1,
                ),
                _rule(id=1, priority=50, pattern_value="netto", matches_subcategory_id=2),
            ],
        )

        with ctx:
            engine = await provider.get(user_id=7)

        result = engine.match("Netto", -50.0)
        assert result is not None
        assert result.subcategory_id == 1  # learned tier won

    @pytest.mark.asyncio()
    async def test_inactive_and_unknown_subcategory_rules_are_skipped(self) -> None:
        provider = _provider([])
        ctx, _ = _patch_user_rules(
            [
                _rule(id=1, active=False),
                _rule(id=2, matches_subcategory_id=12345),  # not in taxonomy map
            ],
        )

        with ctx:
            engine = await provider.get(user_id=7)

        assert engine is provider._engine  # nothing matchable → global only

    @pytest.mark.asyncio()
    async def test_overlay_is_cached_and_invalidate_user_forces_reload(self) -> None:
        provider = _provider([])
        ctx, repo = _patch_user_rules([_rule()])

        with ctx:
            await provider.get(user_id=7)
            await provider.get(user_id=7)
            assert repo.return_value.find_by_user.await_count == 1

            provider.invalidate_user(7)
            await provider.get(user_id=7)
            assert repo.return_value.find_by_user.await_count == 2

    @pytest.mark.asyncio()
    async def test_users_are_isolated(self) -> None:
        """User 8 must not see user 7's rules — each overlay is loaded
        with the requesting user's id."""
        provider = _provider([("netto", "Dagligvarer")])
        ctx, repo = _patch_user_rules([])

        with ctx:
            await provider.get(user_id=7)
            await provider.get(user_id=8)

        called_with = [call.args[0] for call in repo.return_value.find_by_user.await_args_list]
        assert called_with == [7, 8]
