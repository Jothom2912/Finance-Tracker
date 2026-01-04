# backend/migrate_to_elasticsearch.py
"""
Migration script til at migrere data fra MySQL til Elasticsearch.
Følger samme struktur som MySQL databasen.
"""
from elasticsearch import Elasticsearch
from backend.database.mysql import SessionLocal
from backend.models.mysql.transaction import Transaction
from backend.models.mysql.category import Category
from backend.models.mysql.account import Account
from backend.models.mysql.user import User
from backend.models.mysql.budget import Budget
from backend.models.mysql.goal import Goal
from backend.models.mysql.planned_transactions import PlannedTransactions
from backend.models.mysql.account_groups import AccountGroups
from backend.config import ELASTICSEARCH_HOST
from datetime import datetime
from typing import Dict, List
import json

# Elasticsearch client
es = Elasticsearch([ELASTICSEARCH_HOST])

def create_transactions_index():
    """Opretter transactions index med korrekt mapping baseret på MySQL struktur"""
    index_name = "transactions"
    
    # Slet eksisterende index hvis den findes
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    # Mapping der matcher MySQL Transaction struktur
    mapping = {
        "mappings": {
            "properties": {
                "idTransaction": {"type": "integer"},
                "amount": {"type": "float"},
                "description": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "date": {"type": "date", "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd||epoch_millis"},
                "created_at": {"type": "date", "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd||epoch_millis"},
                "type": {"type": "keyword"},  # 'income' eller 'expense'
                "Category_idCategory": {"type": "integer"},
                "category_name": {"type": "keyword"},
                "category_type": {"type": "keyword"},
                "Account_idAccount": {"type": "integer"},
                "account_name": {"type": "keyword"},
                "user_id": {"type": "integer"},
                "username": {"type": "keyword"}
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_categories_index():
    """Opretter categories index med korrekt mapping"""
    index_name = "categories"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idCategory": {"type": "integer"},
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "type": {"type": "keyword"}  # 'income' eller 'expense'
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_accounts_index():
    """Opretter accounts index med korrekt mapping"""
    index_name = "accounts"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idAccount": {"type": "integer"},
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "saldo": {"type": "float"},
                "User_idUser": {"type": "integer"},
                "username": {"type": "keyword"},
                "email": {"type": "keyword"}
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_users_index():
    """Opretter users index med korrekt mapping"""
    index_name = "users"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idUser": {"type": "integer"},
                "username": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "email": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "created_at": {"type": "date", "format": "yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd||epoch_millis"}
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_budgets_index():
    """Opretter budgets index med korrekt mapping"""
    index_name = "budgets"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idBudget": {"type": "integer"},
                "amount": {"type": "float"},
                "budget_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
                "Account_idAccount": {"type": "integer"},
                "account_name": {"type": "keyword"},
                "category_ids": {"type": "integer"}  # Array af category IDs
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_goals_index():
    """Opretter goals index med korrekt mapping"""
    index_name = "goals"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idGoal": {"type": "integer"},
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "target_amount": {"type": "float"},
                "current_amount": {"type": "float"},
                "target_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
                "status": {"type": "keyword"},
                "Account_idAccount": {"type": "integer"},
                "account_name": {"type": "keyword"}
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_account_groups_index():
    """Opretter account_groups index med korrekt mapping"""
    index_name = "account_groups"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idAccountGroups": {"type": "integer"},
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "user_ids": {"type": "integer"}  # Array af user IDs
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def create_planned_transactions_index():
    """Opretter planned_transactions index med korrekt mapping"""
    index_name = "planned_transactions"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  Slettet eksisterende index: {index_name}")
    
    mapping = {
        "mappings": {
            "properties": {
                "idPlannedTransactions": {"type": "integer"},
                "Transaction_idTransaction": {"type": "integer"},
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "amount": {"type": "float"}
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Oprettet index: {index_name}")
    return index_name

def migrate_transactions(db: SessionLocal) -> int:
    """Migrerer alle transaktioner fra MySQL til Elasticsearch"""
    index_name = "transactions"
    
    print(f"\n📦 Migrerer transaktioner...")
    transactions = db.query(Transaction).all()
    print(f"  Fundet {len(transactions)} transaktioner i MySQL")
    
    if len(transactions) == 0:
        print("  ⚠ Ingen transaktioner at migrere")
        return 0
    
    bulk_data = []
    for transaction in transactions:
        try:
            # Hent relaterede data
            category = db.query(Category).filter(
                Category.idCategory == transaction.Category_idCategory
            ).first()
            
            account = db.query(Account).filter(
                Account.idAccount == transaction.Account_idAccount
            ).first()
            
            user = None
            if account:
                user = db.query(User).filter(
                    User.idUser == account.User_idUser
                ).first()
            
            # Opret dokument der matcher MySQL struktur
            # Håndter created_at - brug created_at hvis tilgængelig, ellers brug date eller current time
            created_at = None
            if hasattr(transaction, 'created_at') and transaction.created_at:
                created_at = transaction.created_at.isoformat()
            elif transaction.date:
                created_at = transaction.date.isoformat()
            else:
                created_at = datetime.now().isoformat()
            
            doc = {
                "idTransaction": transaction.idTransaction,
                "amount": float(transaction.amount) if transaction.amount else 0.0,
                "description": transaction.description or "",
                "date": transaction.date.isoformat() if transaction.date else None,
                "created_at": created_at,
                "type": transaction.type or "expense",
                "Category_idCategory": transaction.Category_idCategory,
                "category_name": category.name if category else "Ukendt",
                "category_type": category.type if category else "expense",
                "Account_idAccount": transaction.Account_idAccount,
                "account_name": account.name if account else "Ukendt",
                "user_id": user.idUser if user else None,
                "username": user.username if user else None
            }
            
            # Tilføj til bulk-request
            bulk_data.append({"index": {"_index": index_name, "_id": transaction.idTransaction}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved transaktion {transaction.idTransaction}: {e}")
            continue
    
    # Udfør bulk insert
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede:")
            for item in errors[:5]:  # Vis kun første 5 fejl
                print(f"    - {item['index']['error']}")
        else:
            print(f"  ✓ Succesfuldt migreret {len(transactions)} transaktioner")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(transactions)
    
    return 0

def migrate_categories(db: SessionLocal) -> int:
    """Migrerer alle kategorier fra MySQL til Elasticsearch"""
    index_name = "categories"
    
    print(f"\n📦 Migrerer kategorier...")
    categories = db.query(Category).all()
    print(f"  Fundet {len(categories)} kategorier i MySQL")
    
    if len(categories) == 0:
        print("  ⚠ Ingen kategorier at migrere")
        return 0
    
    bulk_data = []
    for category in categories:
        try:
            doc = {
                "idCategory": category.idCategory,
                "name": category.name,
                "type": category.type
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": category.idCategory}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved kategori {category.idCategory}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(categories)} kategorier")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(categories)
    
    return 0

def migrate_accounts(db: SessionLocal) -> int:
    """Migrerer alle konti fra MySQL til Elasticsearch"""
    index_name = "accounts"
    
    print(f"\n📦 Migrerer konti...")
    accounts = db.query(Account).all()
    print(f"  Fundet {len(accounts)} konti i MySQL")
    
    if len(accounts) == 0:
        print("  ⚠ Ingen konti at migrere")
        return 0
    
    bulk_data = []
    for account in accounts:
        try:
            user = db.query(User).filter(User.idUser == account.User_idUser).first()
            
            doc = {
                "idAccount": account.idAccount,
                "name": account.name,
                "saldo": float(account.saldo) if account.saldo else 0.0,
                "User_idUser": account.User_idUser,
                "username": user.username if user else None,
                "email": user.email if user else None
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": account.idAccount}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved konto {account.idAccount}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(accounts)} konti")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(accounts)
    
    return 0

def migrate_users(db: SessionLocal) -> int:
    """Migrerer alle brugere fra MySQL til Elasticsearch"""
    index_name = "users"
    
    print(f"\n📦 Migrerer brugere...")
    users = db.query(User).all()
    print(f"  Fundet {len(users)} brugere i MySQL")
    
    if len(users) == 0:
        print("  ⚠ Ingen brugere at migrere")
        return 0
    
    bulk_data = []
    for user in users:
        try:
            # IKKE migrer password - sikkerhed!
            doc = {
                "idUser": user.idUser,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": user.idUser}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved bruger {user.idUser}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(users)} brugere")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(users)
    
    return 0

def migrate_budgets(db: SessionLocal) -> int:
    """Migrerer alle budgetter fra MySQL til Elasticsearch"""
    index_name = "budgets"
    
    print(f"\n📦 Migrerer budgetter...")
    budgets = db.query(Budget).all()
    print(f"  Fundet {len(budgets)} budgetter i MySQL")
    
    if len(budgets) == 0:
        print("  ⚠ Ingen budgetter at migrere")
        return 0
    
    bulk_data = []
    for budget in budgets:
        try:
            account = db.query(Account).filter(
                Account.idAccount == budget.Account_idAccount
            ).first()
            
            # Hent kategorier via relationship (hvis tilgængelig)
            category_ids = []
            if hasattr(budget, 'categories') and budget.categories:
                category_ids = [cat.idCategory for cat in budget.categories]
            
            doc = {
                "idBudget": budget.idBudget,
                "amount": float(budget.amount) if budget.amount else 0.0,
                "budget_date": budget.budget_date.isoformat() if budget.budget_date else None,
                "Account_idAccount": budget.Account_idAccount,
                "account_name": account.name if account else "Ukendt",
                "category_ids": category_ids
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": budget.idBudget}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved budget {budget.idBudget}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(budgets)} budgetter")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(budgets)
    
    return 0

def migrate_goals(db: SessionLocal) -> int:
    """Migrerer alle mål fra MySQL til Elasticsearch"""
    index_name = "goals"
    
    print(f"\n🎯 Migrerer mål...")
    goals = db.query(Goal).all()
    print(f"  Fundet {len(goals)} mål i MySQL")
    
    if len(goals) == 0:
        print("  ⚠ Ingen mål at migrere")
        return 0
    
    bulk_data = []
    for goal in goals:
        try:
            account = db.query(Account).filter(
                Account.idAccount == goal.Account_idAccount
            ).first()
            
            doc = {
                "idGoal": goal.idGoal,
                "name": goal.name or "",
                "target_amount": float(goal.target_amount) if goal.target_amount else None,
                "current_amount": float(goal.current_amount) if goal.current_amount else 0.0,
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
                "status": goal.status or "active",
                "Account_idAccount": goal.Account_idAccount,
                "account_name": account.name if account else "Ukendt"
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": goal.idGoal}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved mål {goal.idGoal}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(goals)} mål")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(goals)
    
    return 0

def migrate_account_groups(db: SessionLocal) -> int:
    """Migrerer kontogrupper fra MySQL til Elasticsearch"""
    index_name = "account_groups"
    
    print(f"\n👥 Migrerer kontogrupper...")
    groups = db.query(AccountGroups).all()
    print(f"  Fundet {len(groups)} kontogrupper i MySQL")
    
    if len(groups) == 0:
        print("  ⚠ Ingen kontogrupper at migrere")
        return 0
    
    bulk_data = []
    for group in groups:
        try:
            # Hent user IDs via relationship (hvis tilgængelig)
            user_ids = []
            if hasattr(group, 'users') and group.users:
                user_ids = [user.idUser for user in group.users]
            
            doc = {
                "idAccountGroups": group.idAccountGroups,
                "name": group.name or "",
                "user_ids": user_ids
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": group.idAccountGroups}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved kontogruppe {group.idAccountGroups}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(groups)} kontogrupper")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(groups)
    
    return 0

def migrate_planned_transactions(db: SessionLocal) -> int:
    """Migrerer planlagte transaktioner fra MySQL til Elasticsearch"""
    index_name = "planned_transactions"
    
    print(f"\n📅 Migrerer planlagte transaktioner...")
    planned = db.query(PlannedTransactions).all()
    print(f"  Fundet {len(planned)} planlagte transaktioner i MySQL")
    
    if len(planned) == 0:
        print("  ⚠ Ingen planlagte transaktioner at migrere")
        return 0
    
    bulk_data = []
    for pt in planned:
        try:
            doc = {
                "idPlannedTransactions": pt.idPlannedTransactions,
                "Transaction_idTransaction": pt.Transaction_idTransaction,
                "name": pt.name or "",
                "amount": float(pt.amount) if pt.amount else None
            }
            
            bulk_data.append({"index": {"_index": index_name, "_id": pt.idPlannedTransactions}})
            bulk_data.append(doc)
            
        except Exception as e:
            print(f"  ⚠ Fejl ved planlagt transaktion {pt.idPlannedTransactions}: {e}")
            continue
    
    if bulk_data:
        response = es.bulk(body=bulk_data)
        errors = [item for item in response.get('items', []) if 'error' in item.get('index', {})]
        if errors:
            print(f"  ⚠ {len(errors)} dokumenter fejlede")
        else:
            print(f"  ✓ Succesfuldt migreret {len(planned)} planlagte transaktioner")
        
        es.indices.refresh(index=index_name)
        count = es.count(index=index_name)
        print(f"  📊 Total dokumenter i Elasticsearch: {count['count']}")
        return len(planned)
    
    return 0

def migrate_all():
    """Migrerer alle data fra MySQL til Elasticsearch"""
    print("=" * 60)
    print("🚀 STARTER MIGRATION TIL ELASTICSEARCH")
    print("=" * 60)
    
    # Test Elasticsearch forbindelse
    try:
        print("\n🔍 Tester Elasticsearch forbindelse...")
        health = es.cluster.health()
        print(f"  ✓ Elasticsearch status: {health['status']}")
        print(f"  ✓ Elasticsearch host: {ELASTICSEARCH_HOST}")
    except Exception as e:
        print(f"  ✗ Kan ikke forbinde til Elasticsearch: {e}")
        print("  💡 Sørg for at Elasticsearch kører på", ELASTICSEARCH_HOST)
        return
    
    db = SessionLocal()
    try:
        # Opret alle indices
        print("\n📋 Opretter indices...")
        create_transactions_index()
        create_categories_index()
        create_accounts_index()
        create_users_index()
        create_budgets_index()
        create_goals_index()
        create_account_groups_index()
        create_planned_transactions_index()
        
        # Migrer data (i korrekt rækkefølge pga. foreign keys)
        print("\n" + "=" * 60)
        print("📦 STARTER DATA MIGRATION")
        print("=" * 60)
        
        # 1. Users først (ingen dependencies)
        migrate_users(db)
        
        # 2. Categories (ingen dependencies)
        migrate_categories(db)
        
        # 3. Accounts (afhænger af Users)
        migrate_accounts(db)
        
        # 4. Transactions (afhænger af Categories og Accounts)
        migrate_transactions(db)
        
        # 5. Budgets (afhænger af Accounts)
        migrate_budgets(db)
        
        # 6. Goals (afhænger af Accounts)
        migrate_goals(db)
        
        # 7. Account Groups (afhænger af Users)
        migrate_account_groups(db)
        
        # 8. Planned Transactions (kan være knyttet til Transactions)
        migrate_planned_transactions(db)
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION FULDFØRT!")
        print("=" * 60)
        
        # Vis samlet statistik
        print("\n📊 SAMLET STATISTIK:")
        indices = ["transactions", "categories", "accounts", "users", "budgets", "goals", "account_groups", "planned_transactions"]
        for index_name in indices:
            try:
                count = es.count(index=index_name)
                print(f"  {index_name}: {count['count']} dokumenter")
            except:
                print(f"  {index_name}: 0 dokumenter")
        
    except Exception as e:
        print(f"\n✗ Fejl ved migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_all()
