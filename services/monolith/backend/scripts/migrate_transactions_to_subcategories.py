"""
One-time migration script: backfill subcategory_id on existing transactions.

Strategy:
  1. Load all transactions that have Category_idCategory set but subcategory_id is NULL
  2. For each transaction, run the rule engine to determine subcategory
  3. Update subcategory_id, categorization_tier, categorization_confidence
  4. Leave Category_idCategory untouched (backwards compat for Budget)

Prerequisites:
  - seed_categories.py must have been run first (taxonomy must exist in DB)
  - This script is idempotent: transactions with subcategory_id already set are skipped

Usage:
  cd services/monolith
  uv run python -m backend.scripts.migrate_transactions_to_subcategories
"""

import logging
import sys

from backend.category.adapters.outbound.rule_engine import RuleEngine
from backend.category.application.categorization_service import (
    CategorizationService,
    TransactionInput,
)
from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from backend.database.mysql import SessionLocal
from backend.models.mysql.subcategory import SubCategory
from backend.models.mysql.transaction import Transaction

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate() -> None:
    db = SessionLocal()
    try:
        # Build subcategory lookup
        all_subs = db.query(SubCategory).all()
        subcategory_lookup: dict[str, tuple[int, int]] = {}
        for sub in all_subs:
            subcategory_lookup[sub.name] = (sub.id, sub.category_id)

        if not subcategory_lookup:
            logger.error("No subcategories found. Run seed_categories.py first.")
            sys.exit(1)

        fallback_ids = subcategory_lookup.get("Anden")
        if fallback_ids is None:
            logger.error("Fallback subcategory 'Anden' not found.")
            sys.exit(1)

        keyword_mappings = [
            (kw, mapping["subcategory"])
            for kw, mapping in SEED_MERCHANT_MAPPINGS.items()
        ]

        rule_engine = RuleEngine(
            keyword_mappings=keyword_mappings,
            subcategory_lookup=subcategory_lookup,
        )

        categorization_service = CategorizationService(
            rule_engine=rule_engine,
            fallback_subcategory_id=fallback_ids[0],
            fallback_category_id=fallback_ids[1],
        )

        # Find transactions needing migration
        unmigrated = (
            db.query(Transaction)
            .filter(Transaction.subcategory_id.is_(None))
            .all()
        )

        total = len(unmigrated)
        if total == 0:
            logger.info("All transactions already have subcategory_id set. Nothing to migrate.")
            return

        logger.info("Found %d transactions to migrate.", total)

        migrated = 0
        batch_size = 500

        for txn in unmigrated:
            desc = txn.description or ""
            amount_float = float(txn.amount) if txn.amount else 0.0
            if txn.type == "expense":
                amount_float = -abs(amount_float)

            output = categorization_service.categorize(
                TransactionInput(description=desc, amount=amount_float)
            )

            txn.subcategory_id = output.result.subcategory_id
            txn.categorization_tier = output.result.tier.value
            txn.categorization_confidence = output.result.confidence.value

            migrated += 1

            if migrated % batch_size == 0:
                db.commit()
                logger.info("  Migrated %d/%d...", migrated, total)

        db.commit()
        logger.info("Migration complete: %d/%d transactions updated.", migrated, total)

        # Summary stats
        tier_counts: dict[str, int] = {}
        for txn in unmigrated:
            tier = txn.categorization_tier or "unknown"
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        logger.info("Tier breakdown:")
        for tier, count in sorted(tier_counts.items()):
            logger.info("  %s: %d", tier, count)

    except Exception:
        db.rollback()
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("TRANSACTION MIGRATION: Category -> SubCategory")
    print("=" * 60)
    migrate()
    print("=" * 60)
    print("[DONE] Migration complete.")
    print("=" * 60)
