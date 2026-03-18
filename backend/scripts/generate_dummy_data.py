# backend/generate_dummy_data.py
"""
Script til at generere dummy data til test af migration og applikationen.
Følger korrekt struktur: User → Account → Category → Transaction → Budget → Goal
"""

import io
import sys

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

import bcrypt

from backend.database.mysql import SessionLocal, create_db_tables
from backend.models.mysql.account import Account
from backend.models.mysql.account_groups import AccountGroups
from backend.models.mysql.budget import Budget
from backend.models.mysql.category import Category
from backend.models.mysql.common import account_group_user_association, budget_category_association
from backend.models.mysql.goal import Goal
from backend.models.mysql.planned_transactions import PlannedTransactions
from backend.models.mysql.transaction import Transaction
from backend.models.mysql.user import User

# Minimum counts to guarantee a sizeable dataset
MIN_USERS = 10
MIN_ACCOUNTS = 10
MIN_TRANSACTIONS = 80
MIN_BUDGETS = 10
MIN_GOALS = 10
MIN_PLANNED = 10


def hash_password(password: str) -> str:
    """Hash password using bcrypt (samme metode som auth.py)"""
    password = password[:72]
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def generate_dummy_data(clear_existing: bool = False):
    """
    Genererer dummy data til databasen.

    Args:
        clear_existing: Hvis True, sletter eksisterende data først
    """
    print("=" * 60)
    print("🎲 GENERERER DUMMY DATA")
    print("=" * 60)

    db = SessionLocal()
    try:
        create_db_tables()

        if clear_existing:
            print("\n🗑️  Sletter eksisterende data...")
            db.query(PlannedTransactions).delete()
            db.query(Transaction).delete()
            db.query(Budget).delete()
            db.query(Goal).delete()
            db.query(Account).delete()
            db.query(AccountGroups).delete()
            db.query(Category).delete()
            db.query(User).delete()
            db.commit()
            print("  ✓ Eksisterende data slettet")

        # 1. OPRET USERS
        print("\n👤 Opretter brugere...")
        users = []
        user_data = [
            {"username": "johan", "email": "johan@example.com", "password": "test123"},
            {"username": "marie", "email": "marie@example.com", "password": "test123"},
            {"username": "testuser", "email": "test@example.com", "password": "test123"},
        ]

        while len(user_data) < MIN_USERS:
            idx = len(user_data) + 1
            user_data.append(
                {
                    "username": f"user{idx:02d}",
                    "email": f"user{idx:02d}@example.com",
                    "password": "test123",
                }
            )

        for user_info in user_data:
            # Tjek om user allerede findes (på username ELLER email)
            existing = (
                db.query(User)
                .filter((User.username == user_info["username"]) | (User.email == user_info["email"]))
                .first()
            )

            if not existing:
                # Ingen eksisterende user - opret ny
                user = User(
                    username=user_info["username"],
                    email=user_info["email"],
                    password=hash_password(user_info["password"]),
                    created_at=datetime.now() - timedelta(days=random.randint(30, 365)),
                )
                try:
                    db.add(user)
                    db.flush()  # Flush for at få ID uden commit
                    users.append(user)
                except Exception:
                    # Hvis der er en fejl (fx duplicate key), prøv at hente eksisterende user
                    db.rollback()
                    existing = (
                        db.query(User)
                        .filter((User.username == user_info["username"]) | (User.email == user_info["email"]))
                        .first()
                    )
                    if existing:
                        print(
                            f"  ⚠ User '{user_info['username']}' findes allerede (ID: {existing.idUser}) - bruger eksisterende"
                        )
                        users.append(existing)
                    else:
                        raise  # Re-raise hvis det ikke er en duplicate key fejl
            else:
                # User findes allerede - brug eksisterende
                print(
                    f"  ⚠ User '{user_info['username']}' findes allerede (ID: {existing.idUser}) - bruger eksisterende"
                )
                users.append(existing)

        db.commit()
        for user in users:
            db.refresh(user)
        print(f"  ✓ Oprettet/opdateret {len(users)} brugere")

        # 2. OPRET CATEGORIES (hvis de ikke findes)
        print("\n📁 Opretter kategorier...")
        categories = []
        category_data = [
            {"name": "Mad & Drikke", "type": "expense"},
            {"name": "Transport", "type": "expense"},
            {"name": "Bolig", "type": "expense"},
            {"name": "Fritid", "type": "expense"},
            {"name": "Sundhed", "type": "expense"},
            {"name": "Tøj", "type": "expense"},
            {"name": "Anden", "type": "expense"},
            {"name": "Løn", "type": "income"},
            {"name": "Feriepenge", "type": "income"},
            {"name": "Renter", "type": "income"},
            {"name": "Anden Indkomst", "type": "income"},
        ]

        for cat_info in category_data:
            existing = db.query(Category).filter(Category.name == cat_info["name"]).first()
            if not existing:
                category = Category(name=cat_info["name"], type=cat_info["type"])
                db.add(category)
                categories.append(category)
            else:
                categories.append(existing)

        db.commit()
        for category in categories:
            db.refresh(category)
        print(f"  ✓ Oprettet/opdateret {len(categories)} kategorier")

        # 3. OPRET ACCOUNTS
        print("\n💳 Opretter konti...")
        accounts = []
        account_names = ["Min privat", "Fælles konto", "Opsparing", "Budget konto"]

        for user in users:
            for account_name in account_names[:2] if user.username == "johan" else account_names[:1]:
                account = Account(
                    name=f"{account_name} ({user.username})",
                    saldo=Decimal(random.uniform(1000, 50000)),
                    User_idUser=user.idUser,
                )
                db.add(account)
                accounts.append(account)

        while len(accounts) < MIN_ACCOUNTS and users:
            user = random.choice(users)
            extra_account = Account(
                name=f"Ekstra konto {len(accounts) + 1} ({user.username})",
                saldo=Decimal(random.uniform(1000, 50000)),
                User_idUser=user.idUser,
            )
            db.add(extra_account)
            accounts.append(extra_account)

        db.flush()

        db.commit()
        for account in accounts:
            db.refresh(account)
        print(f"  ✓ Oprettet {len(accounts)} konti")

        # 4. OPRET TRANSACTIONS
        print("\n💰 Opretter transaktioner...")
        transactions = []
        expense_categories = [c for c in categories if c.type == "expense"]
        income_categories = [c for c in categories if c.type == "income"]

        descriptions = [
            "Netto køb",
            "Føtex indkøb",
            "Tankstation",
            "Restaurant besøg",
            "Bilværksted",
            "Husleje",
            "El regning",
            "Internet abonnement",
            "Fitness medlemskab",
            "Tøj køb",
            "Apotek",
            "Kaffe",
            "Lunch",
            "Biograf",
            "Spotify",
        ]

        def make_transaction(account, category, amount, description, t_type):
            transaction = Transaction(
                amount=amount,
                description=description,
                date=datetime.now() - timedelta(days=random.randint(0, 180)),
                type=t_type,
                Category_idCategory=category.idCategory,
                Account_idAccount=account.idAccount,
            )
            db.add(transaction)
            transactions.append(transaction)

        for account in accounts:
            for _ in range(random.randint(20, 50)):
                category = random.choice(expense_categories)
                amount = Decimal(random.uniform(-5000, -50))
                make_transaction(account, category, amount, random.choice(descriptions), "expense")

            for _ in range(random.randint(2, 8)):
                category = random.choice(income_categories)
                amount = Decimal(random.uniform(10000, 50000))
                make_transaction(account, category, amount, f"{category.name} indkomst", "income")

        while len(transactions) < MIN_TRANSACTIONS and accounts:
            account = random.choice(accounts)
            category = random.choice(expense_categories)
            amount = Decimal(random.uniform(-5000, -50))
            make_transaction(account, category, amount, random.choice(descriptions), "expense")

        db.commit()
        for transaction in transactions:
            db.refresh(transaction)
        print(f"  ✓ Oprettet {len(transactions)} transaktioner")

        # 5. OPRET BUDGETS
        print("\n📊 Opretter budgetter...")
        budgets = []

        def add_budget(account, category):
            budget_date = date.today() + timedelta(days=random.randint(-30, 30))
            budget = Budget(
                amount=Decimal(random.uniform(1000, 10000)),
                budget_date=budget_date,
                Account_idAccount=account.idAccount,
            )
            db.add(budget)
            db.flush()
            db.execute(
                budget_category_association.insert().values(
                    Budget_idBudget=budget.idBudget,
                    Category_idCategory=category.idCategory,
                )
            )
            budgets.append(budget)

        for account in accounts[: len(accounts) // 2]:
            for _ in range(random.randint(2, 4)):
                add_budget(account, random.choice(expense_categories))

        while len(budgets) < MIN_BUDGETS and accounts:
            add_budget(random.choice(accounts), random.choice(expense_categories))

        db.commit()
        for budget in budgets:
            db.refresh(budget)
        print(f"  ✓ Oprettet {len(budgets)} budgetter")

        # 6. OPRET GOALS
        print("\n🎯 Opretter mål...")
        goals = []
        goal_names = [
            "Nyt TV",
            "Sommerferie",
            "Bilopsparing",
            "Nyt køkken",
            "Opsparing til hus",
            "Nye møbler",
            "Drømmerejse",
        ]

        def add_goal(account):
            goal_name = random.choice(goal_names)
            target_amount = Decimal(random.uniform(10000, 200000))
            current_amount = Decimal(random.uniform(0, float(target_amount) * 0.7))
            target_date = date.today() + timedelta(days=random.randint(30, 365))
            goal = Goal(
                name=goal_name,
                target_amount=target_amount,
                current_amount=current_amount,
                target_date=target_date,
                status="active" if current_amount < target_amount else "completed",
                Account_idAccount=account.idAccount,
            )
            db.add(goal)
            goals.append(goal)

        for account in accounts[: len(accounts) // 2]:
            add_goal(account)

        while len(goals) < MIN_GOALS and accounts:
            add_goal(random.choice(accounts))

        db.commit()
        for goal in goals:
            db.refresh(goal)
        print(f"  ✓ Oprettet {len(goals)} mål")

        # 7. OPRET ACCOUNT GROUPS (valgfrit)
        print("\n👥 Opretter kontogrupper...")
        account_groups = []

        if len(users) >= 2:
            group = AccountGroups(name="Fælles budget")
            db.add(group)
            db.flush()

            for user in users[:2]:
                db.execute(
                    account_group_user_association.insert().values(
                        AccountGroups_idAccountGroups=group.idAccountGroups,
                        User_idUser=user.idUser,
                    )
                )

            account_groups.append(group)

        db.commit()
        for group in account_groups:
            db.refresh(group)
        print(f"  ✓ Oprettet {len(account_groups)} kontogrupper")

        # 8. OPRET PLANNED TRANSACTIONS (valgfrit)
        print("\n📅 Opretter planlagte transaktioner...")
        planned_transactions = []

        def add_planned(account):
            category = random.choice(expense_categories)
            amount = Decimal(random.uniform(-5000, -100))
            planned = PlannedTransactions(
                Transaction_idTransaction=None,
                name=f"Planlagt: {category.name}",
                amount=amount,
            )
            db.add(planned)
            planned_transactions.append(planned)

        for account in accounts[: len(accounts) // 2]:
            for _ in range(random.randint(1, 3)):
                add_planned(account)

        while len(planned_transactions) < MIN_PLANNED and accounts:
            add_planned(random.choice(accounts))

        db.commit()
        for planned in planned_transactions:
            db.refresh(planned)
        print(f"  ✓ Oprettet {len(planned_transactions)} planlagte transaktioner")

        # VIS STATISTIK
        print("\n" + "=" * 60)
        print("✅ DUMMY DATA GENERERET!")
        print("=" * 60)
        print("\n📊 STATISTIK:")
        print(f"  👤 Brugere: {db.query(User).count()}")
        print(f"  💳 Konti: {db.query(Account).count()}")
        print(f"  📁 Kategorier: {db.query(Category).count()}")
        print(f"  💰 Transaktioner: {db.query(Transaction).count()}")
        print(f"  📊 Budgetter: {db.query(Budget).count()}")
        print(f"  🎯 Mål: {db.query(Goal).count()}")
        print(f"  👥 Kontogrupper: {db.query(AccountGroups).count()}")
        print(f"  📅 Planlagte transaktioner: {db.query(PlannedTransactions).count()}")

        print("\n🔑 LOGIN INFORMATION:")
        print("  Username: johan / Password: test123")
        print("  Username: marie / Password: test123")
        print("  Username: testuser / Password: test123")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Fejl ved generering af dummy data: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    clear = False
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear = True
        print("⚠️  ADVARSEL: Dette vil slette al eksisterende data!")
        response = input("Er du sikker? (ja/nej): ")
        if response.lower() != "ja":
            print("Afbrudt.")
            sys.exit(0)

    generate_dummy_data(clear_existing=clear)
    print("\n✅ Færdig!")
