"""Seed monolith-owned taxonomy (SubCategories, Merchants) and
backfill the MySQL-only ``display_order`` on projected Categories.

Ownership boundaries:

* **Categories** are owned by ``transaction-service``.  The default
  ten-item taxonomy is seeded there via Alembic migrations 005 + 006;
  migration 006 emits ``CategoryCreatedEvent``s that
  ``CategorySyncConsumer`` projects into the MySQL ``Category`` table.
  This script therefore does *not* construct ``Category`` rows — it
  only waits for them to arrive and then enriches them with the
  UI-only ``display_order`` column (which doesn't belong in the event
  contract since transaction-service has no opinion about it).
* **SubCategories** are monolith-only and this script owns them.
* **Merchants** are monolith-only and this script owns them.

Startup ordering assumption:
    The script expects the following services to be running before
    it's invoked:

      * transaction-service (with ``alembic upgrade head`` done)
      * transaction-outbox-worker
      * category-sync-consumer
      * rabbitmq

    If any of the above is down, the projection-verification step
    fails loudly with an actionable error rather than silently
    hanging.  Fully idempotent — safe to run repeatedly.
"""

import time

from backend.category.domain.taxonomy import DEFAULT_TAXONOMY, SEED_MERCHANT_MAPPINGS
from backend.database.mysql import SessionLocal
from backend.models.mysql.category import Category
from backend.models.mysql.merchant import Merchant
from backend.models.mysql.subcategory import SubCategory

_PROJECTION_TIMEOUT_S = 10
_PROJECTION_POLL_INTERVAL_S = 1.0


def seed_categories() -> None:
    """Seed the monolith-owned portion of the taxonomy.

    The Category projection must already be populated by
    ``CategorySyncConsumer`` before subcategories can be linked.
    """
    db = SessionLocal()
    try:
        print("[1/3] Venter paa Category-projektion fra transaction-service...")
        name_to_id = _await_category_projection(db, list(DEFAULT_TAXONOMY.keys()))

        print("[2/3] Opdaterer display_order paa projicerede Categories...")
        _apply_display_order(db, name_to_id)

        print("[3/3] Seeder SubCategories + Merchants...")
        _seed_subcategories(db, name_to_id)
        _seed_merchants(db)

        _print_summary(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _await_category_projection(db, expected_names: list[str]) -> dict[str, int]:
    """Poll MySQL until every expected Category has been projected.

    Rolls back between polls so the session observes new committed
    rows landing via ``CategorySyncConsumer``.  On timeout, raises
    ``RuntimeError`` with enough context to diagnose which part of
    the pipeline is down — no silent hang.
    """
    deadline = time.monotonic() + _PROJECTION_TIMEOUT_S

    while True:
        found = {c.name: c.idCategory for c in db.query(Category).filter(Category.name.in_(expected_names)).all()}
        missing = [n for n in expected_names if n not in found]
        if not missing:
            print(f"  [OK] {len(found)}/{len(expected_names)} Categories fundet i MySQL.")
            return found

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Category-projektion ufuldstaendig efter {_PROJECTION_TIMEOUT_S}s. "
                f"Mangler {len(missing)} kategorier: {missing}. "
                "Tjek at foelgende services koerer:\n"
                "  * transaction-service  (alembic upgrade head skal vaere gennemfoert, inkl. migration 006)\n"
                "  * transaction-outbox-worker  (publicerer category.created til RabbitMQ)\n"
                "  * category-sync-consumer  (projicerer til MySQL Category)\n"
                "  * rabbitmq\n"
                "Brug 'docker compose ps' og 'docker logs <service>' for detaljer."
            )

        db.rollback()
        time.sleep(_PROJECTION_POLL_INTERVAL_S)


def _apply_display_order(db, name_to_id: dict[str, int]) -> None:
    """Set ``display_order`` on projected Categories.

    ``display_order`` is a MySQL-only, UI-presentation concern that
    deliberately isn't part of the cross-service event contract.
    Updating this one column on the projection is the sole write
    operation on ``Category`` in this script — ``name`` and ``type``
    remain event-owned.
    """
    for cat_name, cat_data in DEFAULT_TAXONOMY.items():
        cat_id = name_to_id.get(cat_name)
        if cat_id is None:
            continue
        desired_order = cat_data["order"]
        category = db.query(Category).filter(Category.idCategory == cat_id).first()
        if category is None:
            continue
        if category.display_order != desired_order:
            category.display_order = desired_order
            print(f"  [~] {cat_name} display_order -> {desired_order}")
    db.commit()


def _seed_subcategories(db, name_to_id: dict[str, int]) -> None:
    for cat_name, cat_data in DEFAULT_TAXONOMY.items():
        cat_id = name_to_id.get(cat_name)
        if cat_id is None:
            print(f"  [!] Category {cat_name!r} ikke projiceret — hopper over dens subcategories")
            continue
        for sub_name in cat_data["subcategories"]:
            existing = (
                db.query(SubCategory).filter(SubCategory.name == sub_name, SubCategory.category_id == cat_id).first()
            )
            if existing is None:
                db.add(SubCategory(name=sub_name, category_id=cat_id, is_default=True))
                print(f"    [+] SubCategory: {sub_name}")
    db.commit()
    print("[OK] SubCategories seedet.")


def _seed_merchants(db) -> None:
    sub_lookup: dict[str, int] = {sub.name: sub.id for sub in db.query(SubCategory).all()}

    created = 0
    for keyword, mapping in SEED_MERCHANT_MAPPINGS.items():
        sub_name = mapping["subcategory"]
        display_name = mapping["display"]

        sub_id = sub_lookup.get(sub_name)
        if sub_id is None:
            print(f"  [!] SubCategory '{sub_name}' ikke fundet for keyword '{keyword}' — hopper over")
            continue

        normalized = keyword.lower()
        existing = db.query(Merchant).filter(Merchant.normalized_name == normalized).first()
        if existing is None:
            db.add(
                Merchant(
                    normalized_name=normalized,
                    display_name=display_name,
                    subcategory_id=sub_id,
                    transaction_count=0,
                    is_user_confirmed=False,
                )
            )
            created += 1

    db.commit()
    print(f"[OK] Merchants seedet ({created} nye).")


def _print_summary(db) -> None:
    cat_count = db.query(Category).count()
    sub_count = db.query(SubCategory).count()
    merchant_count = db.query(Merchant).count()
    print(f"\n[Summary] {cat_count} categories, {sub_count} subcategories, {merchant_count} merchants")


if __name__ == "__main__":
    print("=" * 60)
    print("KATEGORI-SEEDING (monolith-ejet: SubCategories + Merchants)")
    print("=" * 60)
    seed_categories()
    print("=" * 60)
    print("[DONE] Seeding afsluttet.")
    print("=" * 60)
