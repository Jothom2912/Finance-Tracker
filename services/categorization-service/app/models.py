from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from messaging import OutboxEventMixin
from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    public_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    semantic_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    taxonomy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    deprecated_in_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replaced_by_public_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class SubCategoryModel(Base):
    __tablename__ = "subcategories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    public_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    semantic_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    taxonomy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    deprecated_in_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replaced_by_public_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MerchantModel(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    subcategory_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    merchant_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CategorizationRuleModel(Base):
    __tablename__ = "categorization_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(30), nullable=False)
    pattern_value: Mapped[str] = mapped_column(Text, nullable=False)
    matches_subcategory_id: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    rule_key: Mapped[str | None] = mapped_column(String(150), nullable=True, unique=True)
    merchant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_field: Mapped[str | None] = mapped_column(String(30), nullable=True)
    match_operator: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    minimum_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    maximum_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())

    __table_args__ = (
        Index("ix_rules_active_priority", "active", "priority"),
        Index("ix_rules_user", "user_id", postgresql_where=("user_id IS NOT NULL")),
        Index(
            "uq_rules_user_pattern",
            "user_id",
            "pattern_type",
            "pattern_value",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
            sqlite_where=text("user_id IS NOT NULL"),
        ),
    )


class CategorizationResultModel(Base):
    __tablename__ = "categorization_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    subcategory_id: Mapped[int] = mapped_column(Integer, nullable=False)
    merchant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MerchantAliasModel(Base):
    __tablename__ = "merchant_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(String(200), nullable=False)
    match_field: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index(
            "uq_merchant_alias_scope",
            "normalized_value",
            "match_field",
            "provider",
            "country",
            unique=True,
        ),
    )


class OutboxEventModel(OutboxEventMixin, Base):
    """Service-owned outbox table; columns come from the shared mixin.

    Kept as a thin local class so Alembic metadata stays service-owned
    (columns and ``ix_outbox_pending_poll`` match the outbox migration exactly).
    """


class ProcessedEventModel(Base):
    """Inbox pattern — deduplication for consumed events.

    ``message_id`` maps to ``BaseEvent.correlation_id`` which is a per-event
    UUID by default.  Named ``message_id`` here to clarify that it deduplicates
    individual messages, not conversation chains.  See docs/SCHEMA.md.
    """

    __tablename__ = "processed_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("uq_processed_events", "message_id", "consumer_name", unique=True),
        Index("ix_processed_at", "processed_at"),
    )
