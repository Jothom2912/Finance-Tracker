"""Enqueue an idempotent full-state taxonomy repair snapshot.

Usage: ``python -m app.tools.repair_taxonomy --run-id incident-2026-08-01``.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from contracts.events.category import CategoryCreatedEvent, SubCategoryCreatedEvent
from sqlalchemy import select

from app.database import async_session_factory
from app.models import CategoryModel, OutboxEventModel, SubCategoryModel

_NAMESPACE = uuid.UUID("38a20d60-d6af-4627-9958-a2ed1a8b9012")


async def enqueue_repair(run_id: str) -> int:
    if not run_id.strip():
        raise ValueError("run_id must not be blank")
    inserted = 0
    async with async_session_factory() as session:
        categories = (
            await session.execute(select(CategoryModel).where(CategoryModel.public_id.is_not(None)))
        ).scalars()
        for category in categories:
            event_id = str(uuid.uuid5(_NAMESPACE, f"{run_id}:category:{category.public_id}"))
            if await session.get(OutboxEventModel, event_id) is not None:
                continue
            category_event = CategoryCreatedEvent(
                event_version=3,
                category_id=category.id,
                name=category.name,
                category_type=category.type,
                display_order=category.display_order,
                public_id=category.public_id,
                semantic_key=category.semantic_key,
                taxonomy_version=category.taxonomy_version,
                lifecycle=category.lifecycle,
                deprecated_in_version=category.deprecated_in_version,
                replaced_by_public_id=category.replaced_by_public_id,
                description=category.description,
                correlation_id=str(uuid.uuid5(_NAMESPACE, f"{run_id}:category:{category.public_id}:message")),
            )
            session.add(
                OutboxEventModel(
                    id=event_id,
                    aggregate_type="category",
                    aggregate_id=str(category.id),
                    event_type=category_event.event_type,
                    payload_json=category_event.to_json(),
                    correlation_id=category_event.correlation_id,
                    status="pending",
                    attempts=0,
                )
            )
            inserted += 1

        subcategories = (
            await session.execute(
                select(SubCategoryModel, CategoryModel.public_id)
                .join(CategoryModel, CategoryModel.id == SubCategoryModel.category_id)
                .where(SubCategoryModel.public_id.is_not(None))
            )
        ).all()
        for subcategory, parent_public_id in subcategories:
            event_id = str(uuid.uuid5(_NAMESPACE, f"{run_id}:subcategory:{subcategory.public_id}"))
            if await session.get(OutboxEventModel, event_id) is not None:
                continue
            subcategory_event = SubCategoryCreatedEvent(
                event_version=3,
                subcategory_id=subcategory.id,
                name=subcategory.name,
                category_id=subcategory.category_id,
                is_default=subcategory.is_default,
                public_id=subcategory.public_id,
                semantic_key=subcategory.semantic_key,
                parent_public_id=parent_public_id,
                taxonomy_version=subcategory.taxonomy_version,
                lifecycle=subcategory.lifecycle,
                deprecated_in_version=subcategory.deprecated_in_version,
                replaced_by_public_id=subcategory.replaced_by_public_id,
                is_fallback=subcategory.is_fallback,
                description=subcategory.description,
                correlation_id=str(uuid.uuid5(_NAMESPACE, f"{run_id}:subcategory:{subcategory.public_id}:message")),
            )
            session.add(
                OutboxEventModel(
                    id=event_id,
                    aggregate_type="subcategory",
                    aggregate_id=str(subcategory.id),
                    event_type=subcategory_event.event_type,
                    payload_json=subcategory_event.to_json(),
                    correlation_id=subcategory_event.correlation_id,
                    status="pending",
                    attempts=0,
                )
            )
            inserted += 1
        await session.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    inserted = asyncio.run(enqueue_repair(args.run_id))
    print(f"enqueued {inserted} taxonomy repair events")


if __name__ == "__main__":
    main()
