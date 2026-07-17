"""F1-03 — CategoryCorrectedConsumer against a REAL sqlite session.

Drives ``handle()`` through the actual models, repository and unique
index (sqlite honors the partial index via ``sqlite_where``) — the
wave-B lesson: a consumer wired to real persistence, not just mocks.
Covers upsert semantics, idempotency and the unlearnable-skip paths.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from app.database import Base
from app.models import CategorizationRuleModel, CategoryModel, ProcessedEventModel, SubCategoryModel
from app.workers.category_corrected_consumer import QUEUE_NAME, CategoryCorrectedConsumer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture()
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                CategoryModel(id=1, name="Mad & drikke", type="expense"),
                SubCategoryModel(id=3, name="Dagligvarer", category_id=1),
                SubCategoryModel(id=5, name="Restaurant", category_id=1),
            ],
        )
        await session.commit()

    yield factory
    await engine.dispose()


def _payload(**overrides: object) -> dict:
    payload = {
        "event_type": "transaction.category_corrected",
        "correlation_id": str(uuid4()),
        "transaction_id": 42,
        "account_id": 1,
        "user_id": 7,
        "description": "NETTO VESTERBRO 12345",
        "category_id": 1,
        "category_name": "Mad & drikke",
        "subcategory_id": 3,
        "subcategory_name": "Dagligvarer",
        "previous_category_id": None,
        "previous_subcategory_id": None,
    }
    payload.update(overrides)
    return payload


async def _consume(session_factory, payload: dict) -> None:
    consumer = CategoryCorrectedConsumer()
    message = AsyncMock()
    message.body = json.dumps(payload).encode("utf-8")
    with patch(
        "app.workers.category_corrected_consumer.async_session_factory",
        session_factory,
    ):
        await consumer.handle(payload, message)


async def _rules(session_factory) -> list[CategorizationRuleModel]:
    async with session_factory() as session:
        result = await session.execute(select(CategorizationRuleModel))
        return list(result.scalars().all())


class TestLearnedRuleUpsert:
    @pytest.mark.asyncio()
    async def test_first_correction_creates_learned_rule(self, session_factory) -> None:
        await _consume(session_factory, _payload())

        rules = await _rules(session_factory)
        assert len(rules) == 1
        rule = rules[0]
        assert rule.user_id == 7
        assert rule.pattern_type == "merchant"
        assert rule.pattern_value == "netto vesterbro"  # normalized, ref-number dropped
        assert rule.matches_subcategory_id == 3
        assert rule.priority == 10
        assert rule.active is True

    @pytest.mark.asyncio()
    async def test_recorrection_retargets_existing_rule(self, session_factory) -> None:
        await _consume(session_factory, _payload())
        await _consume(
            session_factory,
            _payload(description="Netto Vesterbro 99887", subcategory_id=5, subcategory_name="Restaurant"),
        )

        rules = await _rules(session_factory)
        assert len(rules) == 1  # converged on one row despite different ref numbers
        assert rules[0].matches_subcategory_id == 5  # last correction wins

    @pytest.mark.asyncio()
    async def test_recorrection_reactivates_deactivated_rule(self, session_factory) -> None:
        await _consume(session_factory, _payload())
        async with session_factory() as session:
            rule = (await session.execute(select(CategorizationRuleModel))).scalar_one()
            rule.active = False
            await session.commit()

        await _consume(session_factory, _payload())

        rules = await _rules(session_factory)
        assert rules[0].active is True

    @pytest.mark.asyncio()
    async def test_keyword_rule_with_same_pattern_can_coexist(self, session_factory) -> None:
        """The unique index scopes on pattern_type — a user's manual
        KEYWORD rule must not block learning the MERCHANT variant."""
        async with session_factory() as session:
            session.add(
                CategorizationRuleModel(
                    user_id=7,
                    priority=50,
                    pattern_type="keyword",
                    pattern_value="netto vesterbro",
                    matches_subcategory_id=5,
                    active=True,
                ),
            )
            await session.commit()

        await _consume(session_factory, _payload())

        rules = await _rules(session_factory)
        assert len(rules) == 2
        assert {r.pattern_type for r in rules} == {"keyword", "merchant"}


class TestIdempotencyAndSkips:
    @pytest.mark.asyncio()
    async def test_duplicate_message_id_is_noop(self, session_factory) -> None:
        payload = _payload()
        await _consume(session_factory, payload)
        await _consume(session_factory, _payload(correlation_id=payload["correlation_id"], subcategory_id=5))

        rules = await _rules(session_factory)
        assert len(rules) == 1
        assert rules[0].matches_subcategory_id == 3  # duplicate did NOT retarget

    @pytest.mark.asyncio()
    async def test_unlearnable_description_skips_but_records_inbox(self, session_factory) -> None:
        payload = _payload(description="1234 5678")
        await _consume(session_factory, payload)

        assert await _rules(session_factory) == []
        async with session_factory() as session:
            inbox = (
                await session.execute(
                    select(ProcessedEventModel).where(
                        ProcessedEventModel.message_id == payload["correlation_id"],
                        ProcessedEventModel.consumer_name == QUEUE_NAME,
                    ),
                )
            ).scalar_one_or_none()
        assert inbox is not None  # skip is a decision, not a failure — dedup it

    @pytest.mark.asyncio()
    async def test_parent_only_correction_is_skipped(self, session_factory) -> None:
        await _consume(session_factory, _payload(subcategory_id=None, subcategory_name=None))

        assert await _rules(session_factory) == []

    @pytest.mark.asyncio()
    async def test_unknown_subcategory_is_skipped_not_crashed(self, session_factory) -> None:
        """A stale taxonomy read copy upstream must not poison the retry
        loop with FK violations."""
        await _consume(session_factory, _payload(subcategory_id=99999))

        assert await _rules(session_factory) == []
