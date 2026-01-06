#!/usr/bin/env python3
"""
Full Database Sync Script
Synkroniserer ALT data fra MySQL til Elasticsearch og Neo4j
Bruges når data ændres i MySQL og du vil opdatere alle databaser
"""

import sys
import os
from pathlib import Path

# Tilføj backend til path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path.parent))

from elasticsearch import Elasticsearch
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
from backend.config import ELASTICSEARCH_HOST, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from datetime import datetime

# Elasticsearch client
es = Elasticsearch(
    [ELASTICSEARCH_HOST],
    request_timeout=30,
    max_retries=3,
    retry_on_timeout=True,
    headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8", "Content-Type": "application/vnd.elasticsearch+json; compatible-with=8"}
)

# Neo4j driver
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def sync_elasticsearch():
    """Synkroniserer alle data til Elasticsearch"""
    print("\n📊 Synkronisering til Elasticsearch...\n")
    
    try:
        db = SessionLocal()
        
        # 1. Slet alle eksisterende indices
        print("1️⃣ Renser Elasticsearch...")
        indices = ['users', 'accounts', 'categories', 'transactions', 'budgets', 'goals', 'planned_transactions', 'accountgroups']
        for index in indices:
            try:
                if es.indices.exists(index=index):
                    es.indices.delete(index=index)
            except:
                pass
        
        # 2. Opret indices med mappings
        print("2️⃣ Opretter indices...")
        
        es.indices.create(index='users', body={
            "mappings": {
                "properties": {
                    "idUser": {"type": "integer"},
                    "username": {"type": "keyword"},
                    "email": {"type": "keyword"},
                    "created_at": {"type": "date"}
                }
            }
        })
        
        es.indices.create(index='accounts', body={
            "mappings": {
                "properties": {
                    "idAccount": {"type": "integer"},
                    "name": {"type": "text"},
                    "saldo": {"type": "double"},
                    "User_idUser": {"type": "integer"}
                }
            }
        })
        
        es.indices.create(index='categories', body={
            "mappings": {
                "properties": {
                    "idCategory": {"type": "integer"},
                    "name": {"type": "keyword"},
                    "type": {"type": "keyword"}
                }
            }
        })
        
        es.indices.create(index='transactions', body={
            "mappings": {
                "properties": {
                    "idTransaction": {"type": "integer"},
                    "amount": {"type": "double"},
                    "description": {"type": "text"},
                    "date": {"type": "date"},
                    "type": {"type": "keyword"},
                    "Category_idCategory": {"type": "integer"},
                    "Account_idAccount": {"type": "integer"},
                    "created_at": {"type": "date"}
                }
            }
        })
        
        es.indices.create(index='budgets', body={
            "mappings": {
                "properties": {
                    "idBudget": {"type": "integer"},
                    "amount": {"type": "double"},
                    "budget_date": {"type": "date"},
                    "Account_idAccount": {"type": "integer"}
                }
            }
        })
        
        es.indices.create(index='goals', body={
            "mappings": {
                "properties": {
                    "idGoal": {"type": "integer"},
                    "name": {"type": "text"},
                    "target_amount": {"type": "double"},
                    "current_amount": {"type": "double"},
                    "target_date": {"type": "date"},
                    "status": {"type": "keyword"},
                    "Account_idAccount": {"type": "integer"}
                }
            }
        })
        
        es.indices.create(index='planned_transactions', body={
            "mappings": {
                "properties": {
                    "idPlannedTransactions": {"type": "integer"},
                    "Transaction_idTransaction": {"type": "integer"},
                    "name": {"type": "text"},
                    "amount": {"type": "double"}
                }
            }
        })
        
        es.indices.create(index='accountgroups', body={
            "mappings": {
                "properties": {
                    "idAccountGroups": {"type": "integer"},
                    "name": {"type": "text"}
                }
            }
        })
        
        # 3. Hent al data fra MySQL
        print("3️⃣ Henter data fra MySQL...")
        users = db.query(User).all()
        accounts = db.query(Account).all()
        categories = db.query(Category).all()
        transactions = db.query(Transaction).all()
        budgets = db.query(Budget).all()
        goals = db.query(Goal).all()
        planned_transactions = db.query(PlannedTransactions).all()
        account_groups = db.query(AccountGroups).all()
        
        # 4. Upload til Elasticsearch
        print("4️⃣ Uploader til Elasticsearch...")
        
        for user in users:
            es.index(index='users', id=user.idUser, body={
                'idUser': user.idUser,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        print(f"   ✓ {len(users)} brugere")
        
        for account in accounts:
            es.index(index='accounts', id=account.idAccount, body={
                'idAccount': account.idAccount,
                'name': account.name,
                'saldo': float(account.saldo),
                'User_idUser': account.User_idUser
            })
        print(f"   ✓ {len(accounts)} konti")
        
        for category in categories:
            es.index(index='categories', id=category.idCategory, body={
                'idCategory': category.idCategory,
                'name': category.name,
                'type': category.type
            })
        print(f"   ✓ {len(categories)} kategorier")
        
        for transaction in transactions:
            es.index(index='transactions', id=transaction.idTransaction, body={
                'idTransaction': transaction.idTransaction,
                'amount': float(transaction.amount),
                'description': transaction.description,
                'date': transaction.date.isoformat() if transaction.date else None,
                'type': transaction.type,
                'Category_idCategory': transaction.Category_idCategory,
                'Account_idAccount': transaction.Account_idAccount,
                'created_at': transaction.created_at.isoformat() if transaction.created_at else None
            })
        print(f"   ✓ {len(transactions)} transaktioner")
        
        for budget in budgets:
            es.index(index='budgets', id=budget.idBudget, body={
                'idBudget': budget.idBudget,
                'amount': float(budget.amount),
                'budget_date': budget.budget_date.isoformat() if budget.budget_date else None,
                'Account_idAccount': budget.Account_idAccount
            })
        print(f"   ✓ {len(budgets)} budgetter")
        
        for goal in goals:
            es.index(index='goals', id=goal.idGoal, body={
                'idGoal': goal.idGoal,
                'name': goal.name,
                'target_amount': float(goal.target_amount),
                'current_amount': float(goal.current_amount),
                'target_date': goal.target_date.isoformat() if goal.target_date else None,
                'status': goal.status,
                'Account_idAccount': goal.Account_idAccount
            })
        print(f"   ✓ {len(goals)} mål")
        
        for pt in planned_transactions:
            es.index(index='planned_transactions', id=pt.idPlannedTransactions, body={
                'idPlannedTransactions': pt.idPlannedTransactions,
                'Transaction_idTransaction': pt.Transaction_idTransaction,
                'name': pt.name,
                'amount': float(pt.amount)
            })
        print(f"   ✓ {len(planned_transactions)} planlagte transaktioner")
        
        for ag in account_groups:
            es.index(index='accountgroups', id=ag.idAccountGroups, body={
                'idAccountGroups': ag.idAccountGroups,
                'name': ag.name
            })
        print(f"   ✓ {len(account_groups)} kontogrupper")
        
        print("\n✅ Elasticsearch synkroniseret!")
        db.close()
        
    except Exception as e:
        print(f"\n❌ Elasticsearch fejl: {e}")
        raise

def sync_neo4j():
    """Synkroniserer alle data til Neo4j"""
    print("\n🔗 Synkronisering til Neo4j...\n")
    
    try:
        db = SessionLocal()
        
        with neo4j_driver.session() as session:
            # 1. Slet alt data
            print("1️⃣ Renser Neo4j...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # 2. Opret constraints
            print("2️⃣ Opretter constraints...")
            constraints = [
                "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.idUser IS UNIQUE",
                "CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.idAccount IS UNIQUE",
                "CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.idCategory IS UNIQUE",
                "CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.idTransaction IS UNIQUE",
                "CREATE CONSTRAINT budget_id IF NOT EXISTS FOR (b:Budget) REQUIRE b.idBudget IS UNIQUE",
                "CREATE CONSTRAINT goal_id IF NOT EXISTS FOR (g:Goal) REQUIRE g.idGoal IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except:
                    pass
            
            # 3. Hent data fra MySQL
            print("3️⃣ Henter data fra MySQL...")
            users = db.query(User).all()
            accounts = db.query(Account).all()
            categories = db.query(Category).all()
            transactions = db.query(Transaction).all()
            budgets = db.query(Budget).all()
            goals = db.query(Goal).all()
            planned_transactions = db.query(PlannedTransactions).all()
            account_groups = db.query(AccountGroups).all()
            
            # 4. Upload til Neo4j
            print("4️⃣ Uploader til Neo4j...")
            
            for user in users:
                session.run(
                    "CREATE (u:User {idUser: $id, username: $username, email: $email, created_at: $created_at})",
                    id=user.idUser,
                    username=user.username,
                    email=user.email,
                    created_at=user.created_at.isoformat() if user.created_at else None
                )
            print(f"   ✓ {len(users)} brugere")
            
            for ag in account_groups:
                session.run(
                    "CREATE (ag:AccountGroup {idAccountGroups: $id, name: $name})",
                    id=ag.idAccountGroups,
                    name=ag.name
                )
            print(f"   ✓ {len(account_groups)} kontogrupper")
            
            for account in accounts:
                session.run(
                    "CREATE (a:Account {idAccount: $id, name: $name, saldo: $saldo})",
                    id=account.idAccount,
                    name=account.name,
                    saldo=float(account.saldo)
                )
                session.run(
                    "MATCH (u:User {idUser: $user_id}) MATCH (a:Account {idAccount: $account_id}) CREATE (a)-[:BELONGS_TO]->(u)",
                    user_id=account.User_idUser,
                    account_id=account.idAccount
                )
            print(f"   ✓ {len(accounts)} konti")
            
            for category in categories:
                session.run(
                    "CREATE (c:Category {idCategory: $id, name: $name, type: $type})",
                    id=category.idCategory,
                    name=category.name,
                    type=category.type
                )
            print(f"   ✓ {len(categories)} kategorier")
            
            for transaction in transactions:
                session.run(
                    "CREATE (t:Transaction {idTransaction: $id, amount: $amount, description: $description, date: $date, type: $type})",
                    id=transaction.idTransaction,
                    amount=float(transaction.amount),
                    description=transaction.description,
                    date=transaction.date.isoformat() if transaction.date else None,
                    type=transaction.type
                )
                session.run(
                    "MATCH (a:Account {idAccount: $account_id}) MATCH (t:Transaction {idTransaction: $trans_id}) CREATE (t)-[:IN_ACCOUNT]->(a)",
                    account_id=transaction.Account_idAccount,
                    trans_id=transaction.idTransaction
                )
                session.run(
                    "MATCH (c:Category {idCategory: $category_id}) MATCH (t:Transaction {idTransaction: $trans_id}) CREATE (t)-[:IN_CATEGORY]->(c)",
                    category_id=transaction.Category_idCategory,
                    trans_id=transaction.idTransaction
                )
            print(f"   ✓ {len(transactions)} transaktioner")
            
            for budget in budgets:
                session.run(
                    "CREATE (b:Budget {idBudget: $id, amount: $amount, budget_date: $date})",
                    id=budget.idBudget,
                    amount=float(budget.amount),
                    date=budget.budget_date.isoformat() if budget.budget_date else None
                )
                session.run(
                    "MATCH (a:Account {idAccount: $account_id}) MATCH (b:Budget {idBudget: $budget_id}) CREATE (b)-[:FOR_ACCOUNT]->(a)",
                    account_id=budget.Account_idAccount,
                    budget_id=budget.idBudget
                )
            print(f"   ✓ {len(budgets)} budgetter")
            
            for goal in goals:
                session.run(
                    "CREATE (g:Goal {idGoal: $id, name: $name, target_amount: $target, current_amount: $current, target_date: $date, status: $status})",
                    id=goal.idGoal,
                    name=goal.name,
                    target=float(goal.target_amount),
                    current=float(goal.current_amount),
                    date=goal.target_date.isoformat() if goal.target_date else None,
                    status=goal.status
                )
                session.run(
                    "MATCH (a:Account {idAccount: $account_id}) MATCH (g:Goal {idGoal: $goal_id}) CREATE (g)-[:FOR_ACCOUNT]->(a)",
                    account_id=goal.Account_idAccount,
                    goal_id=goal.idGoal
                )
            print(f"   ✓ {len(goals)} mål")
            
            for pt in planned_transactions:
                session.run(
                    "CREATE (pt:PlannedTransaction {idPlannedTransactions: $id, name: $name, amount: $amount})",
                    id=pt.idPlannedTransactions,
                    name=pt.name,
                    amount=float(pt.amount)
                )
                session.run(
                    "MATCH (t:Transaction {idTransaction: $trans_id}) MATCH (pt:PlannedTransaction {idPlannedTransactions: $pt_id}) CREATE (pt)-[:REFERENCES]->(t)",
                    trans_id=pt.Transaction_idTransaction,
                    pt_id=pt.idPlannedTransactions
                )
            print(f"   ✓ {len(planned_transactions)} planlagte transaktioner")
        
        print("\n✅ Neo4j synkroniseret!")
        db.close()
        
    except Exception as e:
        print(f"\n❌ Neo4j fejl: {e}")
        raise

def main():
    print("=" * 70)
    print("🔄 FULL DATABASE SYNC - Synkroniserer ALT data")
    print("=" * 70)
    print("\nDette vil synkronisere ALT data fra MySQL til:")
    print("  • Elasticsearch")
    print("  • Neo4j")
    print("\nBrug dette når du har ændret data i MySQL og vil opdatere alle")
    print("databaser til den aktuelle tilstand.")
    
    input("\n⏱️  Tryk Enter for at starte synkronisering...")
    
    try:
        sync_elasticsearch()
        sync_neo4j()
        
        print("\n" + "=" * 70)
        print("✅ ALT DATA ER SYNKRONISERET!")
        print("=" * 70)
        print("\nAlle databaser er nu identiske.")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Kritisk fejl: {e}")
        sys.exit(1)
    finally:
        neo4j_driver.close()

if __name__ == "__main__":
    main()
