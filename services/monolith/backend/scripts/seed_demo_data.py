"""
Seed realistic demo data for the dashboard.

Creates:
  - 1 Account (if not exists)
  - 1 BankConnection (Nordea sandbox)
  - ~120 transactions spread over 6 months with mixed categorization tiers
  - 1 MonthlyBudget with budget lines for current month
  - 2 Goals

Idempotent: checks for existing demo account before inserting.
Run: uv run python -m backend.scripts.seed_demo_data
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.database.mysql import SessionLocal
from backend.models.mysql.account import Account
from backend.models.mysql.bank_connection import BankConnection
from backend.models.mysql.category import Category
from backend.models.mysql.goal import Goal
from backend.models.mysql.monthly_budget import BudgetLine, MonthlyBudget
from backend.models.mysql.subcategory import SubCategory
from backend.models.mysql.transaction import Transaction

DEMO_ACCOUNT_NAME = "Min Konto"
DEMO_USER_ID = 1

EXPENSE_TEMPLATES = [
    {"desc": "Dankort-nota Netto Koebenhavn", "amount": (85, 350), "tier": "rule"},
    {"desc": "Visa koeb REMA 1000", "amount": (120, 500), "tier": "rule"},
    {"desc": "Dankort-nota Foetex City", "amount": (95, 420), "tier": "rule"},
    {"desc": "Visa koeb LIDL Amager", "amount": (55, 280), "tier": "rule"},
    {"desc": "Dankort-nota 7-Eleven Noerreport", "amount": (25, 89), "tier": "rule"},
    {"desc": "Betalingsservice Husleje marts", "amount": (6500, 6500), "tier": "rule"},
    {"desc": "Overfoersel Andelsforening", "amount": (1200, 1200), "tier": "fallback"},
    {"desc": "PBS Elgiganten A/S", "amount": (299, 2499), "tier": "rule"},
    {"desc": "Visa koeb MURRES CAFE KBH", "amount": (85, 245), "tier": "rule"},
    {"desc": "Dankort-nota Starbucks Stroget", "amount": (42, 78), "tier": "rule"},
    {"desc": "Visa koeb DSB Pendlerkort", "amount": (380, 380), "tier": "rule"},
    {"desc": "Visa koeb MOVIA Rejsekort", "amount": (50, 150), "tier": "rule"},
    {"desc": "PBS Fitness World", "amount": (249, 249), "tier": "rule"},
    {"desc": "Betalingsservice TRYG Forsikring", "amount": (450, 450), "tier": "fallback"},
    {"desc": "Overfoersel Netflix", "amount": (89, 89), "tier": "rule"},
    {"desc": "Visa koeb Spotify AB", "amount": (79, 79), "tier": "rule"},
    {"desc": "Visa koeb POWER Taastrup", "amount": (199, 1999), "tier": "rule"},
    {"desc": "Dankort-nota Matas Frederiksberg", "amount": (79, 349), "tier": "fallback"},
    {"desc": "Visa koeb H&M Online", "amount": (199, 599), "tier": "rule"},
    {"desc": "Visa koeb ZARA Koebenhavn", "amount": (299, 899), "tier": "fallback"},
    {"desc": "Dankort-nota Apotek Noerrebro", "amount": (49, 189), "tier": "fallback"},
    {"desc": "Visa koeb BAUHAUS Glostrup", "amount": (149, 799), "tier": "fallback"},
    {"desc": "Overfoersel til opsparing", "amount": (500, 2000), "tier": "fallback"},
    {"desc": "Visa koeb Wolt Food Delivery", "amount": (89, 299), "tier": "rule"},
    {"desc": "Dankort-nota Cafe Halvvejen KBH", "amount": (65, 185), "tier": "rule"},
]

INCOME_TEMPLATES = [
    {"desc": "Loen fra Arbejdsgiver A/S", "amount": (28000, 32000), "tier": "rule"},
    {"desc": "Overfoersel SU-stipendium", "amount": (6397, 6397), "tier": "fallback"},
    {"desc": "Tilbagebetaling forsikring", "amount": (250, 800), "tier": "fallback"},
]


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        account = _ensure_account(db)
        categories = _get_categories(db)
        if not categories:
            print("[!] No categories found. Run seed_categories first:")
            print("    uv run python -m backend.scripts.seed_categories")
            return

        subcategories = _get_subcategories(db)
        _seed_bank_connection(db, account.idAccount)
        _seed_transactions(db, account.idAccount, categories, subcategories)
        _seed_monthly_budget(db, account.idAccount, categories)
        _seed_goals(db, account.idAccount)

        db.commit()
        _print_summary(db, account.idAccount)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _ensure_account(db) -> Account:
    existing = db.query(Account).filter(Account.name == DEMO_ACCOUNT_NAME).first()
    if existing:
        print(f"  [~] Account exists: {DEMO_ACCOUNT_NAME} (id={existing.idAccount})")
        return existing

    account = Account(name=DEMO_ACCOUNT_NAME, saldo=Decimal("45230.50"), User_idUser=DEMO_USER_ID)
    db.add(account)
    db.flush()
    print(f"  [+] Account created: {DEMO_ACCOUNT_NAME} (id={account.idAccount})")
    return account


def _get_categories(db) -> dict[str, int]:
    cats = db.query(Category).all()
    return {c.name: c.idCategory for c in cats}


def _get_subcategories(db) -> dict[int, list]:
    subs = db.query(SubCategory).all()
    result: dict[int, list] = {}
    for s in subs:
        result.setdefault(s.category_id, []).append(s)
    return result


def _seed_bank_connection(db, account_id: int) -> None:
    existing = (
        db.query(BankConnection)
        .filter(
            BankConnection.account_id == account_id,
            BankConnection.bank_name == "Nordea",
        )
        .first()
    )
    if existing:
        existing.last_synced_at = datetime.utcnow() - timedelta(hours=2)
        print("  [~] BankConnection exists (Nordea), updated last_synced_at")
        return

    conn = BankConnection(
        account_id=account_id,
        session_id="demo-session-nordea-sandbox",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="demo-uid-nordea-001",
        bank_account_iban="DK5000400440116243",
        status="active",
        last_synced_at=datetime.utcnow() - timedelta(hours=2),
        expires_at=datetime.utcnow() + timedelta(days=85),
    )
    db.add(conn)
    print("  [+] BankConnection created: Nordea (DK)")


def _seed_transactions(db, account_id: int, categories: dict, subcategories: dict) -> None:
    existing_count = db.query(Transaction).filter(Transaction.Account_idAccount == account_id).count()
    if existing_count > 50:
        print(f"  [~] Already {existing_count} transactions for account, skipping seed")
        return

    expense_cat_names = ["Mad & drikke", "Bolig", "Transport", "Underholdning", "Shopping", "Sundhed"]
    income_cat_names = ["Indkomst"]

    expense_cat_id = None
    income_cat_id = None
    for name, cid in categories.items():
        if name in expense_cat_names and expense_cat_id is None:
            expense_cat_id = cid
        if name in income_cat_names:
            income_cat_id = cid

    if expense_cat_id is None:
        expense_cat_id = next(iter(categories.values()))
    if income_cat_id is None:
        income_cat_id = expense_cat_id

    expense_cat_ids = [cid for name, cid in categories.items() if name in expense_cat_names]
    if not expense_cat_ids:
        expense_cat_ids = list(categories.values())

    today = date.today()
    created = 0

    for month_offset in range(6):
        month_date = date(today.year, today.month, 1) - timedelta(days=30 * month_offset)
        days_in_month = 28

        income_count = random.randint(1, 2)
        for _ in range(income_count):
            tmpl = random.choice(INCOME_TEMPLATES)
            amount = Decimal(str(random.randint(tmpl["amount"][0], tmpl["amount"][1])))
            tx_day = random.randint(1, min(28, days_in_month))
            tx_date = month_date.replace(day=tx_day)
            if tx_date > today:
                tx_date = today

            cat_id = income_cat_id
            sub_id = _pick_subcategory(subcategories, cat_id)

            tx = Transaction(
                amount=amount,
                description=tmpl["desc"],
                date=tx_date,
                type="income",
                Category_idCategory=cat_id,
                Account_idAccount=account_id,
                subcategory_id=sub_id,
                categorization_tier=tmpl["tier"],
                categorization_confidence="high" if tmpl["tier"] == "rule" else None,
            )
            db.add(tx)
            created += 1

        expense_count = random.randint(15, 22)
        for _ in range(expense_count):
            tmpl = random.choice(EXPENSE_TEMPLATES)
            raw = random.randint(tmpl["amount"][0], tmpl["amount"][1])
            amount = Decimal(str(-raw))
            tx_day = random.randint(1, min(28, days_in_month))
            tx_date = month_date.replace(day=tx_day)
            if tx_date > today:
                tx_date = today

            cat_id = random.choice(expense_cat_ids)
            sub_id = _pick_subcategory(subcategories, cat_id)

            tx = Transaction(
                amount=amount,
                description=tmpl["desc"],
                date=tx_date,
                type="expense",
                Category_idCategory=cat_id,
                Account_idAccount=account_id,
                subcategory_id=sub_id,
                categorization_tier=tmpl["tier"],
                categorization_confidence="high" if tmpl["tier"] == "rule" else None,
            )
            db.add(tx)
            created += 1

    print(f"  [+] Created {created} transactions across 6 months")


def _pick_subcategory(subcategories: dict, category_id: int) -> int | None:
    subs = subcategories.get(category_id, [])
    if not subs:
        return None
    return random.choice(subs).id


def _seed_monthly_budget(db, account_id: int, categories: dict) -> None:
    today = date.today()
    existing = (
        db.query(MonthlyBudget)
        .filter(
            MonthlyBudget.account_id == account_id,
            MonthlyBudget.month == today.month,
            MonthlyBudget.year == today.year,
        )
        .first()
    )
    if existing:
        print(f"  [~] MonthlyBudget already exists for {today.year}-{today.month:02d}")
        return

    budget = MonthlyBudget(
        month=today.month,
        year=today.year,
        account_id=account_id,
    )
    db.add(budget)
    db.flush()

    budget_amounts = {
        "Mad & drikke": 4000,
        "Bolig": 7000,
        "Transport": 800,
        "Underholdning": 1500,
        "Shopping": 2000,
        "Sundhed": 500,
    }

    lines_created = 0
    for cat_name, amount in budget_amounts.items():
        cat_id = categories.get(cat_name)
        if cat_id is None:
            continue
        line = BudgetLine(
            monthly_budget_id=budget.id,
            category_id=cat_id,
            amount=Decimal(str(amount)),
        )
        db.add(line)
        lines_created += 1

    print(f"  [+] MonthlyBudget created for {today.year}-{today.month:02d} with {lines_created} lines")


def _seed_goals(db, account_id: int) -> None:
    existing = db.query(Goal).filter(Goal.Account_idAccount == account_id).count()
    if existing > 0:
        print(f"  [~] {existing} goals already exist, skipping")
        return

    goals = [
        Goal(
            name="Noedfond",
            target_amount=Decimal("50000"),
            current_amount=Decimal("32500"),
            target_date=date(2026, 12, 31),
            status="active",
            Account_idAccount=account_id,
        ),
        Goal(
            name="Ferie Spanien",
            target_amount=Decimal("15000"),
            current_amount=Decimal("8200"),
            target_date=date(2026, 7, 1),
            status="active",
            Account_idAccount=account_id,
        ),
    ]

    for g in goals:
        db.add(g)
    print(f"  [+] Created {len(goals)} goals")


def _print_summary(db, account_id: int) -> None:
    tx_count = db.query(Transaction).filter(Transaction.Account_idAccount == account_id).count()
    rule_count = (
        db.query(Transaction)
        .filter(
            Transaction.Account_idAccount == account_id,
            Transaction.categorization_tier == "rule",
        )
        .count()
    )
    fallback_count = (
        db.query(Transaction)
        .filter(
            Transaction.Account_idAccount == account_id,
            Transaction.categorization_tier == "fallback",
        )
        .count()
    )
    bank_count = db.query(BankConnection).filter(BankConnection.account_id == account_id).count()
    goal_count = db.query(Goal).filter(Goal.Account_idAccount == account_id).count()

    print("\n" + "=" * 50)
    print("DEMO DATA SUMMARY")
    print("=" * 50)
    print(f"  Transactions:    {tx_count}")
    print(f"    - rule tier:   {rule_count}")
    print(f"    - fallback:    {fallback_count}")
    print(f"  Bank connections: {bank_count}")
    print(f"  Goals:           {goal_count}")
    print("=" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("SEEDING DEMO DATA FOR DASHBOARD")
    print("=" * 50)
    seed_demo_data()
    print("\n[DONE] Demo data seeded.")
    print("Open http://localhost:3001 to see the dashboard.")
