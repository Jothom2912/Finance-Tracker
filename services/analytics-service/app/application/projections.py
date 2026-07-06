"""Projektorer: contract-events → projection store-kald.

Hver projektor ejer ét domænes event-typer og normaliserer payload-
varianter (fx ``account.created`` der bruger ``account_name`` hvor
``account.updated`` bruger ``name``). Idempotens/ordering håndteres i
stores via timestamp-guards — projektorerne er bevidst tilstandsløse.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal

from contracts.base import BaseEvent
from contracts.events.account import AccountCreatedEvent, AccountUpdatedEvent
from contracts.events.category import (
    CategoryCreatedEvent,
    CategoryDeletedEvent,
    CategoryUpdatedEvent,
    SubCategoryCreatedEvent,
    SubCategoryDeletedEvent,
    SubCategoryUpdatedEvent,
)
from contracts.events.goal import GoalCreatedEvent, GoalDeletedEvent, GoalUpdatedEvent
from contracts.events.transaction import (
    TransactionCategorizedEvent,
    TransactionCreatedEvent,
    TransactionDeletedEvent,
    TransactionUpdatedEvent,
)

from app.application.ports.outbound import (
    IAccountProjectionStore,
    IGoalProjectionStore,
    ITaxonomyProjectionStore,
    ITransactionProjectionStore,
)


def event_ts_millis(event: BaseEvent) -> int:
    return int(event.timestamp.timestamp() * 1000)


def _amount(raw: str) -> float:
    return float(Decimal(raw))


class TransactionProjector:
    def __init__(
        self,
        store: ITransactionProjectionStore,
        taxonomy_store: ITaxonomyProjectionStore,
    ) -> None:
        self._store = store
        self._taxonomy = taxonomy_store

    async def handle_created_or_updated(self, event: TransactionCreatedEvent | TransactionUpdatedEvent) -> None:
        # Core-events bærer subcategory_id men intet navn — slå op i
        # taxonomy-projektionen; None self-heales af senere
        # transaction.categorized (som bærer navnet).
        subcategory_name: str | None = None
        if event.subcategory_id is not None:
            subcategory_name = await self._taxonomy.get_subcategory_name(event.subcategory_id)

        await self._store.upsert_core(
            transaction_id=event.transaction_id,
            account_id=event.account_id,
            user_id=event.user_id,
            amount=_amount(event.amount),
            transaction_type=event.transaction_type.lower(),
            tx_date=event.tx_date,
            description=event.description,
            category_id=event.category_id,
            category_name=event.category or None,
            subcategory_id=event.subcategory_id,
            subcategory_name=subcategory_name,
            categorization_tier=event.categorization_tier,
            categorization_confidence=event.categorization_confidence,
            event_ts=event_ts_millis(event),
        )

    async def handle_categorized(self, event: TransactionCategorizedEvent) -> None:
        await self._store.apply_categorization(
            transaction_id=event.transaction_id,
            category_id=event.category_id,
            category_name=event.category_name,
            subcategory_id=event.subcategory_id,
            subcategory_name=event.subcategory_name,
            categorization_tier=event.tier,
            categorization_confidence=event.confidence,
            event_ts=event_ts_millis(event),
        )

    async def handle_deleted(self, event: TransactionDeletedEvent) -> None:
        await self._store.mark_deleted(
            transaction_id=event.transaction_id,
            event_ts=event_ts_millis(event),
        )


class AccountProjector:
    def __init__(self, store: IAccountProjectionStore) -> None:
        self._store = store

    async def handle_created(self, event: AccountCreatedEvent) -> None:
        await self._store.upsert(
            account_id=event.account_id,
            user_id=event.user_id,
            name=event.account_name,
            saldo=_amount(event.saldo),
            budget_start_day=event.budget_start_day,
            event_ts=event_ts_millis(event),
        )

    async def handle_updated(self, event: AccountUpdatedEvent) -> None:
        await self._store.upsert(
            account_id=event.account_id,
            user_id=event.user_id,
            name=event.name,
            saldo=_amount(event.saldo),
            budget_start_day=event.budget_start_day,
            event_ts=event_ts_millis(event),
        )


class TaxonomyProjector:
    def __init__(self, store: ITaxonomyProjectionStore) -> None:
        self._store = store

    async def handle_category(self, event: CategoryCreatedEvent | CategoryUpdatedEvent | CategoryDeletedEvent) -> None:
        applied = await self._store.upsert_category(
            category_id=event.category_id,
            name=event.name,
            category_type=event.category_type,
            display_order=event.display_order,
            is_deleted=isinstance(event, CategoryDeletedEvent),
            event_ts=event_ts_millis(event),
        )
        # Denormaliserede navne på transaktioner opdateres kun ved
        # anvendte renames — et stale event må ikke rulle navne tilbage.
        # Ved delete beholder transaktionerne det sidste kendte navn
        # (samme degraderings-semantik som gatewayens fallback).
        if applied and isinstance(event, CategoryUpdatedEvent):
            await self._store.propagate_category_rename(category_id=event.category_id, name=event.name)

    async def handle_subcategory(
        self,
        event: SubCategoryCreatedEvent | SubCategoryUpdatedEvent | SubCategoryDeletedEvent,
    ) -> None:
        applied = await self._store.upsert_subcategory(
            subcategory_id=event.subcategory_id,
            category_id=event.category_id,
            name=event.name,
            is_default=event.is_default,
            is_deleted=isinstance(event, SubCategoryDeletedEvent),
            event_ts=event_ts_millis(event),
        )
        if applied and isinstance(event, SubCategoryUpdatedEvent):
            await self._store.propagate_subcategory_rename(subcategory_id=event.subcategory_id, name=event.name)


class GoalProjector:
    def __init__(self, store: IGoalProjectionStore) -> None:
        self._store = store

    async def handle_created_or_updated(self, event: GoalCreatedEvent | GoalUpdatedEvent) -> None:
        await self._store.upsert(
            goal_id=event.goal_id,
            user_id=event.user_id,
            name=event.name,
            target_amount=_amount(event.target_amount),
            current_amount=_amount(event.current_amount),
            target_date=event.target_date,
            status=event.status,
            is_deleted=False,
            event_ts=event_ts_millis(event),
        )

    async def handle_deleted(self, event: GoalDeletedEvent) -> None:
        await self._store.mark_deleted(goal_id=event.goal_id, event_ts=event_ts_millis(event))


EventHandler = Callable[[BaseEvent], Awaitable[None]]
Registry = dict[str, tuple[type[BaseEvent], EventHandler]]


def build_registry(
    transactions: TransactionProjector,
    accounts: AccountProjector,
    taxonomy: TaxonomyProjector,
    goals: GoalProjector,
) -> Registry:
    """event_type → (kontrakt-klasse, handler).

    Event-typer udenfor registret (fx ``account.creation_failed``,
    ``bank.*``) acker workeren som bevidst ignorerede.
    """
    registry: Registry = {}

    def register(event_cls: type[BaseEvent], handler: Callable[..., Awaitable[None]]) -> None:
        event_type = event_cls.model_fields["event_type"].default
        registry[event_type] = (event_cls, handler)

    register(TransactionCreatedEvent, transactions.handle_created_or_updated)
    register(TransactionUpdatedEvent, transactions.handle_created_or_updated)
    register(TransactionCategorizedEvent, transactions.handle_categorized)
    register(TransactionDeletedEvent, transactions.handle_deleted)

    register(AccountCreatedEvent, accounts.handle_created)
    register(AccountUpdatedEvent, accounts.handle_updated)

    register(CategoryCreatedEvent, taxonomy.handle_category)
    register(CategoryUpdatedEvent, taxonomy.handle_category)
    register(CategoryDeletedEvent, taxonomy.handle_category)
    register(SubCategoryCreatedEvent, taxonomy.handle_subcategory)
    register(SubCategoryUpdatedEvent, taxonomy.handle_subcategory)
    register(SubCategoryDeletedEvent, taxonomy.handle_subcategory)

    register(GoalCreatedEvent, goals.handle_created_or_updated)
    register(GoalUpdatedEvent, goals.handle_created_or_updated)
    register(GoalDeletedEvent, goals.handle_deleted)

    return registry


__all__ = [
    "AccountProjector",
    "EventHandler",
    "GoalProjector",
    "Registry",
    "TaxonomyProjector",
    "TransactionProjector",
    "build_registry",
    "event_ts_millis",
]
