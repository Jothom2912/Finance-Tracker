# backend/migrate_to_neo4j.py
"""
Migration script til at migrere data fra MySQL til Neo4j.
Følger samme struktur som MySQL databasen, men som graph nodes og relationships.
"""
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from neo4j import GraphDatabase
from backend.database.mysql import SessionLocal
from backend.models.mysql.transaction import Transaction
from backend.models.mysql.category import Category
from backend.models.mysql.account import Account
from backend.models.mysql.user import User
from backend.models.mysql.budget import Budget
from backend.models.mysql.goal import Goal
from backend.models.mysql.planned_transactions import PlannedTransactions
from backend.models.mysql.account_groups import AccountGroups
from backend.config import ELASTICSEARCH_HOST, NEO4J_URI, NEO4J_USER
import os
from datetime import datetime
from decimal import Decimal

# Neo4j driver - bruger centraliseret connection
from backend.database.neo4j import get_neo4j_driver

def clear_neo4j_database(driver):
    """Sletter alle nodes og relationships i Neo4j"""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        print("  ✓ Slettet alle eksisterende data i Neo4j")

def create_constraints(driver):
    """Opretter constraints og indexes i Neo4j"""
    with driver.session() as session:
        # Unique constraints
        constraints = [
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.idUser IS UNIQUE",
            "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.idAccount IS UNIQUE",
            "CREATE CONSTRAINT category_id_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.idCategory IS UNIQUE",
            "CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS FOR (t:Transaction) REQUIRE t.idTransaction IS UNIQUE",
            "CREATE CONSTRAINT budget_id_unique IF NOT EXISTS FOR (b:Budget) REQUIRE b.idBudget IS UNIQUE",
            "CREATE CONSTRAINT goal_id_unique IF NOT EXISTS FOR (g:Goal) REQUIRE g.idGoal IS UNIQUE",
            "CREATE CONSTRAINT account_group_id_unique IF NOT EXISTS FOR (ag:AccountGroup) REQUIRE ag.idAccountGroups IS UNIQUE",
            "CREATE CONSTRAINT planned_transaction_id_unique IF NOT EXISTS FOR (pt:PlannedTransaction) REQUIRE pt.idPlannedTransactions IS UNIQUE",
        ]
        
        for constraint in constraints:
            try:
                session.run(constraint)
            except Exception as e:
                # Constraint eksisterer måske allerede
                pass
        
        print("  ✓ Constraints oprettet")

def migrate_users(driver, db: SessionLocal) -> int:
    """Migrerer alle brugere fra MySQL til Neo4j"""
    print(f"\n👤 Migrerer brugere...")
    users = db.query(User).all()
    print(f"  Fundet {len(users)} brugere i MySQL")
    
    if len(users) == 0:
        print("  ⚠ Ingen brugere at migrere")
        return 0
    
    with driver.session() as session:
        for user in users:
            query = """
            MERGE (u:User {idUser: $idUser})
            ON CREATE SET 
                u.username = $username,
                u.email = $email,
                u.created_at = $created_at
            ON MATCH SET
                u.username = $username,
                u.email = $email,
                u.created_at = $created_at
            """
            session.run(query, {
                "idUser": user.idUser,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None
            })
    
    print(f"  ✓ Succesfuldt migreret {len(users)} brugere")
    return len(users)

def migrate_categories(driver, db: SessionLocal) -> int:
    """Migrerer alle kategorier fra MySQL til Neo4j"""
    print(f"\n📁 Migrerer kategorier...")
    categories = db.query(Category).all()
    print(f"  Fundet {len(categories)} kategorier i MySQL")
    
    if len(categories) == 0:
        print("  ⚠ Ingen kategorier at migrere")
        return 0
    
    with driver.session() as session:
        for category in categories:
            query = """
            MERGE (c:Category {idCategory: $idCategory})
            ON CREATE SET 
                c.name = $name,
                c.type = $type
            ON MATCH SET
                c.name = $name,
                c.type = $type
            """
            session.run(query, {
                "idCategory": category.idCategory,
                "name": category.name,
                "type": category.type
            })
    
    print(f"  ✓ Succesfuldt migreret {len(categories)} kategorier")
    return len(categories)

def migrate_accounts(driver, db: SessionLocal) -> int:
    """Migrerer alle konti fra MySQL til Neo4j med relationships til Users"""
    print(f"\n💳 Migrerer konti...")
    accounts = db.query(Account).all()
    print(f"  Fundet {len(accounts)} konti i MySQL")
    
    if len(accounts) == 0:
        print("  ⚠ Ingen konti at migrere")
        return 0
    
    with driver.session() as session:
        for account in accounts:
            # Opret Account node
            query = """
            MATCH (u:User {idUser: $userId})
            MERGE (a:Account {idAccount: $idAccount})
            ON CREATE SET 
                a.name = $name,
                a.saldo = $saldo
            ON MATCH SET
                a.name = $name,
                a.saldo = $saldo
            MERGE (u)-[:OWNS]->(a)
            """
            session.run(query, {
                "idAccount": account.idAccount,
                "name": account.name,
                "saldo": float(account.saldo) if account.saldo else 0.0,
                "userId": account.User_idUser
            })
    
    print(f"  ✓ Succesfuldt migreret {len(accounts)} konti")
    return len(accounts)

def migrate_transactions(driver, db: SessionLocal) -> int:
    """Migrerer alle transaktioner fra MySQL til Neo4j med relationships"""
    print(f"\n💰 Migrerer transaktioner...")
    transactions = db.query(Transaction).all()
    print(f"  Fundet {len(transactions)} transaktioner i MySQL")
    
    if len(transactions) == 0:
        print("  ⚠ Ingen transaktioner at migrere")
        return 0
    
    with driver.session() as session:
        for transaction in transactions:
            # Opret Transaction node med relationships
            # Håndter created_at - brug created_at hvis tilgængelig, ellers brug date eller current time
            created_at = None
            if hasattr(transaction, 'created_at') and transaction.created_at:
                created_at = transaction.created_at.isoformat()
            elif transaction.date:
                created_at = transaction.date.isoformat()
            else:
                from datetime import datetime
                created_at = datetime.now().isoformat()
            
            query = """
            MATCH (a:Account {idAccount: $accountId})
            MATCH (c:Category {idCategory: $categoryId})
            MERGE (t:Transaction {idTransaction: $idTransaction})
            ON CREATE SET 
                t.amount = $amount,
                t.description = $description,
                t.date = $date,
                t.type = $type,
                t.created_at = $created_at
            ON MATCH SET
                t.amount = $amount,
                t.description = $description,
                t.date = $date,
                t.type = $type,
                t.created_at = $created_at
            MERGE (a)-[:HAS_TRANSACTION]->(t)
            MERGE (t)-[:BELONGS_TO_CATEGORY]->(c)
            """
            session.run(query, {
                "idTransaction": transaction.idTransaction,
                "amount": float(transaction.amount) if transaction.amount else 0.0,
                "description": transaction.description or "",
                "date": transaction.date.isoformat() if transaction.date else None,
                "type": transaction.type or "expense",
                "created_at": created_at,
                "accountId": transaction.Account_idAccount,
                "categoryId": transaction.Category_idCategory
            })
    
    print(f"  ✓ Succesfuldt migreret {len(transactions)} transaktioner")
    return len(transactions)

def migrate_budgets(driver, db: SessionLocal) -> int:
    """Migrerer alle budgetter fra MySQL til Neo4j med relationships"""
    print(f"\n📊 Migrerer budgetter...")
    budgets = db.query(Budget).all()
    print(f"  Fundet {len(budgets)} budgetter i MySQL")
    
    if len(budgets) == 0:
        print("  ⚠ Ingen budgetter at migrere")
        return 0
    
    with driver.session() as session:
        for budget in budgets:
            # Opret Budget node
            query = """
            MATCH (a:Account {idAccount: $accountId})
            MERGE (b:Budget {idBudget: $idBudget})
            ON CREATE SET 
                b.amount = $amount,
                b.budget_date = $budget_date
            ON MATCH SET
                b.amount = $amount,
                b.budget_date = $budget_date
            MERGE (a)-[:HAS_BUDGET]->(b)
            """
            session.run(query, {
                "idBudget": budget.idBudget,
                "amount": float(budget.amount) if budget.amount else 0.0,
                "budget_date": budget.budget_date.isoformat() if budget.budget_date else None,
                "accountId": budget.Account_idAccount
            })
            
            # Tilføj Category relationships (fra association table)
            # Vi skal hente categories fra MySQL
            if hasattr(budget, 'categories') and budget.categories:
                for category in budget.categories:
                    link_query = """
                    MATCH (b:Budget {idBudget: $budgetId})
                    MATCH (c:Category {idCategory: $categoryId})
                    MERGE (b)-[:FOR_CATEGORY]->(c)
                    """
                    session.run(link_query, {
                        "budgetId": budget.idBudget,
                        "categoryId": category.idCategory
                    })
    
    print(f"  ✓ Succesfuldt migreret {len(budgets)} budgetter")
    return len(budgets)

def migrate_goals(driver, db: SessionLocal) -> int:
    """Migrerer alle mål fra MySQL til Neo4j med relationships"""
    print(f"\n🎯 Migrerer mål...")
    goals = db.query(Goal).all()
    print(f"  Fundet {len(goals)} mål i MySQL")
    
    if len(goals) == 0:
        print("  ⚠ Ingen mål at migrere")
        return 0
    
    with driver.session() as session:
        for goal in goals:
            query = """
            MATCH (a:Account {idAccount: $accountId})
            MERGE (g:Goal {idGoal: $idGoal})
            ON CREATE SET 
                g.name = $name,
                g.target_amount = $target_amount,
                g.current_amount = $current_amount,
                g.target_date = $target_date,
                g.status = $status
            ON MATCH SET
                g.name = $name,
                g.target_amount = $target_amount,
                g.current_amount = $current_amount,
                g.target_date = $target_date,
                g.status = $status
            MERGE (a)-[:HAS_GOAL]->(g)
            """
            session.run(query, {
                "idGoal": goal.idGoal,
                "name": goal.name or "",
                "target_amount": float(goal.target_amount) if goal.target_amount else None,
                "current_amount": float(goal.current_amount) if goal.current_amount else 0.0,
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
                "status": goal.status or "active",
                "accountId": goal.Account_idAccount
            })
    
    print(f"  ✓ Succesfuldt migreret {len(goals)} mål")
    return len(goals)

def migrate_account_groups(driver, db: SessionLocal) -> int:
    """Migrerer kontogrupper fra MySQL til Neo4j"""
    print(f"\n👥 Migrerer kontogrupper...")
    groups = db.query(AccountGroups).all()
    print(f"  Fundet {len(groups)} kontogrupper i MySQL")
    
    if len(groups) == 0:
        print("  ⚠ Ingen kontogrupper at migrere")
        return 0
    
    with driver.session() as session:
        for group in groups:
            # Opret AccountGroup node
            query = """
            MERGE (ag:AccountGroup {idAccountGroups: $idAccountGroups})
            ON CREATE SET 
                ag.name = $name
            ON MATCH SET
                ag.name = $name
            """
            session.run(query, {
                "idAccountGroups": group.idAccountGroups,
                "name": group.name or ""
            })
            
            # Tilføj User relationships (fra association table)
            if hasattr(group, 'users') and group.users:
                for user in group.users:
                    link_query = """
                    MATCH (ag:AccountGroup {idAccountGroups: $groupId})
                    MATCH (u:User {idUser: $userId})
                    MERGE (u)-[:MEMBER_OF]->(ag)
                    """
                    session.run(link_query, {
                        "groupId": group.idAccountGroups,
                        "userId": user.idUser
                    })
    
    print(f"  ✓ Succesfuldt migreret {len(groups)} kontogrupper")
    return len(groups)

def migrate_planned_transactions(driver, db: SessionLocal) -> int:
    """Migrerer planlagte transaktioner fra MySQL til Neo4j"""
    print(f"\n📅 Migrerer planlagte transaktioner...")
    planned = db.query(PlannedTransactions).all()
    print(f"  Fundet {len(planned)} planlagte transaktioner i MySQL")
    
    if len(planned) == 0:
        print("  ⚠ Ingen planlagte transaktioner at migrere")
        return 0
    
    with driver.session() as session:
        for pt in planned:
            # Opret PlannedTransaction node
            query = """
            MERGE (pt:PlannedTransaction {idPlannedTransactions: $idPlannedTransactions})
            ON CREATE SET 
                pt.name = $name,
                pt.amount = $amount
            ON MATCH SET
                pt.name = $name,
                pt.amount = $amount
            """
            session.run(query, {
                "idPlannedTransactions": pt.idPlannedTransactions,
                "name": pt.name or "",
                "amount": float(pt.amount) if pt.amount else None
            })
            
            # Hvis der er en knyttet Transaction, opret relationship
            if pt.Transaction_idTransaction:
                link_query = """
                MATCH (pt:PlannedTransaction {idPlannedTransactions: $ptId})
                MATCH (t:Transaction {idTransaction: $transactionId})
                MERGE (pt)-[:PLANNED_FOR]->(t)
                """
                session.run(link_query, {
                    "ptId": pt.idPlannedTransactions,
                    "transactionId": pt.Transaction_idTransaction
                })
    
    print(f"  ✓ Succesfuldt migreret {len(planned)} planlagte transaktioner")
    return len(planned)

def migrate_all():
    """Migrerer alle data fra MySQL til Neo4j"""
    print("=" * 60)
    print("🚀 STARTER MIGRATION TIL NEO4J")
    print("=" * 60)
    
    # Test Neo4j forbindelse
    driver = None
    try:
        print(f"\n🔍 Tester Neo4j forbindelse...")
        print(f"  URI: {NEO4J_URI}")
        print(f"  User: {NEO4J_USER}")
        driver = get_neo4j_driver()
        driver.verify_connectivity()
        print(f"  ✓ Forbindelse til Neo4j OK")
    except Exception as e:
        print(f"  ✗ Kan ikke forbinde til Neo4j: {e}")
        print(f"  💡 Sørg for at Neo4j kører på {NEO4J_URI}")
        print(f"  💡 Tjek NEO4J_USER og NEO4J_PASSWORD i .env")
        return
    
    db = SessionLocal()
    try:
        # Slet eksisterende data (valgfrit - kommenter ud hvis du vil beholde data)
        # MERGE statements håndterer eksisterende data, så sletning er ikke nødvendig
        # men kan være nyttig for at starte forfra
        print("\n🗑️  Sletter eksisterende Neo4j data...")
        clear_neo4j_database(driver)
        
        # Opret constraints
        print("\n📋 Opretter constraints...")
        create_constraints(driver)
        
        # Migrer data (i korrekt rækkefølge pga. relationships)
        print("\n" + "=" * 60)
        print("📦 STARTER DATA MIGRATION")
        print("=" * 60)
        
        # 1. Users først (ingen dependencies)
        migrate_users(driver, db)
        
        # 2. Categories (ingen dependencies)
        migrate_categories(driver, db)
        
        # 3. Accounts (afhænger af Users)
        migrate_accounts(driver, db)
        
        # 4. Transactions (afhænger af Accounts og Categories)
        migrate_transactions(driver, db)
        
        # 5. Budgets (afhænger af Accounts)
        migrate_budgets(driver, db)
        
        # 6. Goals (afhænger af Accounts)
        migrate_goals(driver, db)
        
        # 7. Account Groups (afhænger af Users)
        migrate_account_groups(driver, db)
        
        # 8. Planned Transactions (kan være knyttet til Transactions)
        migrate_planned_transactions(driver, db)
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION FULDFØRT!")
        print("=" * 60)
        
        # Vis statistik
        print("\n📊 STATISTIK:")
        with driver.session() as session:
            stats = {
                "User": session.run("MATCH (u:User) RETURN count(u) as count").single()["count"],
                "Account": session.run("MATCH (a:Account) RETURN count(a) as count").single()["count"],
                "Category": session.run("MATCH (c:Category) RETURN count(c) as count").single()["count"],
                "Transaction": session.run("MATCH (t:Transaction) RETURN count(t) as count").single()["count"],
                "Budget": session.run("MATCH (b:Budget) RETURN count(b) as count").single()["count"],
                "Goal": session.run("MATCH (g:Goal) RETURN count(g) as count").single()["count"],
                "AccountGroup": session.run("MATCH (ag:AccountGroup) RETURN count(ag) as count").single()["count"],
                "PlannedTransaction": session.run("MATCH (pt:PlannedTransaction) RETURN count(pt) as count").single()["count"],
            }
            for label, count in stats.items():
                print(f"  {label}: {count} nodes")
        
    except Exception as e:
        print(f"\n✗ Fejl ved migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        if driver:
            driver.close()

if __name__ == "__main__":
    migrate_all()

