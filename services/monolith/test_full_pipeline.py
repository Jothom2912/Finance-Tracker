"""
Full pipeline integration test:
  Enable Banking session -> fetch transactions -> categorize -> store in DB

Tests the complete flow: sync -> deduplicate -> rule engine -> persist
Reports rule engine hit-rate as baseline for ML/LLM decisions.
"""

import os
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv(os.path.join("..", "..", ".env"))

from backend.banking.adapters.outbound.enable_banking_client import (
    EnableBankingClient,
    EnableBankingConfig,
)
from backend.banking.application.service import BankingService
from backend.category.adapters.outbound.mysql_repository import (
    MySQLCategoryRepository,
)
from backend.category.adapters.outbound.mysql_subcategory_repository import (
    MySQLSubCategoryRepository,
)
from backend.category.adapters.outbound.rule_engine import RuleEngine
from backend.category.application.categorization_service import CategorizationService
from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from backend.database.mysql import SessionLocal, create_db_tables
from backend.models.mysql.bank_connection import BankConnection
from backend.models.mysql.transaction import Transaction

SESSION_ID = "a08d92f0-7ed6-499a-971f-e739bf44efee"
ACCOUNT_ID = 1

key_path = os.getenv("ENABLE_BANKING_KEY_PATH", "./enablebanking-sandbox.pem")
if not os.path.isabs(key_path):
    key_path = os.path.join("..", "..", key_path)

config = EnableBankingConfig(
    app_id=os.getenv("ENABLE_BANKING_APP_ID", ""),
    key_path=key_path,
    redirect_uri=os.getenv("ENABLE_BANKING_REDIRECT_URI", ""),
    environment=os.getenv("ENABLE_BANKING_ENVIRONMENT", "sandbox"),
)

print("=" * 70)
print("  FULL PIPELINE TEST: Bank -> Categorize -> Store")
print("=" * 70)

print(f"\nConfig OK: app_id={config.app_id[:8]}...")
print(f"Database:  {os.getenv('DATABASE_URL', '?').split('@')[0]}@***")

print("\n--- Step 1: Ensure DB tables exist ---")
create_db_tables()

db = SessionLocal()
client = EnableBankingClient(config)

try:
    print("\n--- Step 2: Build categorization service ---")
    sub_repo = MySQLSubCategoryRepository(db)
    all_subs = sub_repo.get_all()
    cat_repo = MySQLCategoryRepository(db)
    all_cats = cat_repo.get_all()

    if not all_subs or not all_cats:
        print("ERROR: No categories/subcategories in DB. Run seed_categories.py first.")
        print(f"  Categories: {len(all_cats)}, SubCategories: {len(all_subs)}")
        sys.exit(1)

    cat_id_lookup = {cat.id: cat.id for cat in all_cats}
    subcategory_lookup: dict[str, tuple[int, int]] = {}
    for sub in all_subs:
        if sub.category_id in cat_id_lookup:
            subcategory_lookup[sub.name] = (sub.id, sub.category_id)

    keyword_mappings = [(kw, mapping["subcategory"]) for kw, mapping in SEED_MERCHANT_MAPPINGS.items()]

    rule_engine = RuleEngine(
        keyword_mappings=keyword_mappings,
        subcategory_lookup=subcategory_lookup,
    )

    fallback_ids = subcategory_lookup.get("Anden")
    if fallback_ids is None:
        print("ERROR: Fallback subcategory 'Anden' not found.")
        sys.exit(1)

    categorization_service = CategorizationService(
        rule_engine=rule_engine,
        fallback_subcategory_id=fallback_ids[0],
        fallback_category_id=fallback_ids[1],
    )
    print(f"  Categories: {len(all_cats)}")
    print(f"  SubCategories: {len(all_subs)}")
    print(f"  Keyword mappings: {len(keyword_mappings)}")
    print(f"  Fallback: subcategory_id={fallback_ids[0]}, category_id={fallback_ids[1]}")

    print("\n--- Step 3: Create BankConnection records ---")
    session_data = client.get_session(SESSION_ID)
    account_uids = session_data.get("accounts", [])
    aspsp = session_data.get("aspsp", {})
    print(f"  Bank: {aspsp.get('name')} ({aspsp.get('country')})")
    print(f"  Session accounts: {len(account_uids)}")

    connections_created = 0
    for uid in account_uids:
        existing = db.query(BankConnection).filter(BankConnection.bank_account_uid == uid).first()
        if existing:
            existing.session_id = SESSION_ID
            existing.status = "active"
            print(f"  Updated: {uid[:12]}... (id={existing.id})")
        else:
            conn = BankConnection(
                account_id=ACCOUNT_ID,
                session_id=SESSION_ID,
                bank_name=aspsp.get("name", "Nordea"),
                bank_country=aspsp.get("country", "DK"),
                bank_account_uid=uid,
                bank_account_iban="",
                status="active",
            )
            db.add(conn)
            db.flush()
            connections_created += 1
            print(f"  Created: {uid[:12]}... (id={conn.id})")
    db.commit()
    print(f"  Total: {connections_created} new connections")

    print("\n--- Step 4: Sync transactions (fetch + categorize + store) ---")
    active_connections = (
        db.query(BankConnection)
        .filter(
            BankConnection.session_id == SESSION_ID,
            BankConnection.status == "active",
        )
        .all()
    )

    banking_service = BankingService(
        db=db,
        banking_client=client,
        categorization_service=categorization_service,
    )

    total_fetched = 0
    total_imported = 0
    total_dupes = 0
    total_errors = 0

    for conn in active_connections:
        print(f"\n  Syncing connection {conn.id} ({conn.bank_account_uid[:12]}...):")
        result = banking_service.sync_transactions(connection_id=conn.id)
        print(f"    Fetched: {result.total_fetched}")
        print(f"    New:     {result.new_imported}")
        print(f"    Dupes:   {result.duplicates_skipped}")
        print(f"    Errors:  {result.errors}")
        total_fetched += result.total_fetched
        total_imported += result.new_imported
        total_dupes += result.duplicates_skipped
        total_errors += result.errors

    print(f"\n  TOTALS: {total_fetched} fetched, {total_imported} imported, {total_dupes} dupes, {total_errors} errors")

    print("\n--- Step 5: Analyze categorization results ---")
    synced_txns = (
        db.query(Transaction)
        .filter(Transaction.Account_idAccount == ACCOUNT_ID)
        .order_by(Transaction.date.desc())
        .all()
    )

    tier_counts = Counter()
    subcategory_counts = Counter()
    fallback_descriptions = []

    for txn in synced_txns:
        tier = txn.categorization_tier or "none"
        tier_counts[tier] += 1

        if txn.subcategory_id and txn.subcategory:
            subcategory_counts[txn.subcategory.name] += 1
        if tier == "fallback":
            fallback_descriptions.append(txn.description or "?")

    total_txns = len(synced_txns)
    rule_hits = tier_counts.get("rule", 0)
    fallback_hits = tier_counts.get("fallback", 0)
    hit_rate = (rule_hits / total_txns * 100) if total_txns > 0 else 0

    print(f"\n  Total transactions in DB: {total_txns}")
    print("\n  Categorization tiers:")
    for tier, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
        pct = count / total_txns * 100 if total_txns > 0 else 0
        print(f"    {tier:12s}: {count:4d}  ({pct:.1f}%)")

    print(f"\n  RULE ENGINE HIT RATE: {rule_hits}/{total_txns} = {hit_rate:.1f}%")
    print(
        f"  FALLBACK RATE:        {fallback_hits}/{total_txns} = {(fallback_hits / total_txns * 100) if total_txns else 0:.1f}%"
    )

    if subcategory_counts:
        print("\n  Top subcategories (rule engine hits):")
        for sub_name, count in subcategory_counts.most_common(15):
            print(f"    {sub_name:25s}: {count:4d}")

    unique_fallbacks = Counter(fallback_descriptions)
    if unique_fallbacks:
        print(f"\n  Unique fallback descriptions ({len(unique_fallbacks)} unique):")
        for desc, count in unique_fallbacks.most_common(20):
            print(f"    [{count:3d}x] {desc[:65]}")

    print("\n" + "=" * 70)
    print("  PIPELINE TEST COMPLETE")
    print("=" * 70)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
finally:
    client.close()
    db.close()
