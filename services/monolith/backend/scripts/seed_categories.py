"""
Script til at seede det nye kategori-hierarki i databasen.

Seeder:
  1. Category (top-level) med display_order og type
  2. SubCategory under hver Category
  3. Merchant entries fra SEED_MERCHANT_MAPPINGS

Fully idempotent — checks by name before insert, safe to run repeatedly.
"""

from backend.category.domain.taxonomy import DEFAULT_TAXONOMY, SEED_MERCHANT_MAPPINGS
from backend.category.domain.value_objects import CategoryType
from backend.database.mysql import SessionLocal
from backend.models.mysql.category import Category
from backend.models.mysql.merchant import Merchant
from backend.models.mysql.subcategory import SubCategory


def seed_categories() -> None:
    """Seed the full Category -> SubCategory hierarchy + Merchant entries."""
    db = SessionLocal()
    try:
        _seed_taxonomy(db)
        _seed_merchants(db)
        _print_summary(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed_taxonomy(db) -> None:
    """Seed Categories and SubCategories from DEFAULT_TAXONOMY."""
    for cat_name, cat_data in DEFAULT_TAXONOMY.items():
        cat_type: CategoryType = cat_data["type"]
        display_order: int = cat_data["order"]
        subcategories: list[str] = cat_data["subcategories"]

        existing_cat = db.query(Category).filter(Category.name == cat_name).first()
        if existing_cat is None:
            existing_cat = Category(
                name=cat_name,
                type=cat_type.value,
                display_order=display_order,
            )
            db.add(existing_cat)
            db.flush()
            print(f"  [+] Category: {cat_name} ({cat_type.value}, order={display_order})")
        else:
            if existing_cat.display_order != display_order:
                existing_cat.display_order = display_order
                db.flush()
                print(f"  [~] Category updated display_order: {cat_name} -> {display_order}")

        for sub_name in subcategories:
            existing_sub = (
                db.query(SubCategory)
                .filter(
                    SubCategory.name == sub_name,
                    SubCategory.category_id == existing_cat.idCategory,
                )
                .first()
            )
            if existing_sub is None:
                sub = SubCategory(
                    name=sub_name,
                    category_id=existing_cat.idCategory,
                    is_default=True,
                )
                db.add(sub)
                print(f"    [+] SubCategory: {sub_name}")

    db.commit()
    print("[OK] Taxonomy seeded.")


def _seed_merchants(db) -> None:
    """Seed Merchant entries from SEED_MERCHANT_MAPPINGS."""
    sub_lookup: dict[str, int] = {}
    for sub in db.query(SubCategory).all():
        sub_lookup[sub.name] = sub.id

    created = 0
    for keyword, mapping in SEED_MERCHANT_MAPPINGS.items():
        sub_name = mapping["subcategory"]
        display_name = mapping["display"]

        sub_id = sub_lookup.get(sub_name)
        if sub_id is None:
            print(f"  [!] SubCategory '{sub_name}' not found for keyword '{keyword}' — skipping")
            continue

        normalized = keyword.lower()
        existing = db.query(Merchant).filter(Merchant.normalized_name == normalized).first()
        if existing is None:
            merchant = Merchant(
                normalized_name=normalized,
                display_name=display_name,
                subcategory_id=sub_id,
                transaction_count=0,
                is_user_confirmed=False,
            )
            db.add(merchant)
            created += 1

    db.commit()
    print(f"[OK] Merchants seeded ({created} new).")


def _print_summary(db) -> None:
    cat_count = db.query(Category).count()
    sub_count = db.query(SubCategory).count()
    merchant_count = db.query(Merchant).count()
    print(f"\n[Summary] {cat_count} categories, {sub_count} subcategories, {merchant_count} merchants")


if __name__ == "__main__":
    print("=" * 60)
    print("KATEGORI SEEDING SCRIPT (ny taxonomi)")
    print("=" * 60)
    seed_categories()
    print("=" * 60)
    print("[DONE] Seeding afsluttet.")
    print("=" * 60)
