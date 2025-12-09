# backend/graphql/resolvers.py
"""
GraphQL resolvers - Håndterer data hentning fra Neo4j eller MySQL
"""
from typing import List, Optional
from datetime import datetime
from backend.database import SessionLocal
from backend.models.transaction import Transaction as TransactionModel
from backend.models.category import Category as CategoryModel
from backend.models.account import Account as AccountModel
from backend.models.user import User as UserModel
from backend.models.budget import Budget as BudgetModel
from backend.models.goal import Goal as GoalModel
from backend.graphql.schema import (
    User, Category, Account, Transaction, Budget, Goal,
    TransactionFilter, TransactionCreate
)
from neo4j import GraphDatabase
import os

# Neo4j konfiguration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

USE_NEO4J = os.getenv("USE_NEO4J", "false").lower() == "true"

def get_neo4j_driver():
    """Opretter Neo4j driver"""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# ============================================================================
# USER RESOLVERS
# ============================================================================

async def get_users() -> List[User]:
    """Hent alle brugere"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run("MATCH (u:User) RETURN u ORDER BY u.idUser")
            users = [User(
                idUser=record["u"]["idUser"],
                username=record["u"]["username"],
                email=record["u"]["email"],
                created_at=datetime.fromisoformat(record["u"]["created_at"]) if record["u"].get("created_at") else None
            ) for record in result]
        driver.close()
        return users
    else:
        db = SessionLocal()
        try:
            users = db.query(UserModel).all()
            return [User(
                idUser=u.idUser,
                username=u.username,
                email=u.email,
                created_at=u.created_at
            ) for u in users]
        finally:
            db.close()

async def get_user(id: int) -> Optional[User]:
    """Hent specifik bruger"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run("MATCH (u:User {idUser: $id}) RETURN u", id=id)
            record = result.single()
            if record:
                u = record["u"]
                return User(
                    idUser=u["idUser"],
                    username=u["username"],
                    email=u["email"],
                    created_at=datetime.fromisoformat(u["created_at"]) if u.get("created_at") else None
                )
        driver.close()
        return None
    else:
        db = SessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.idUser == id).first()
            if user:
                return User(
                    idUser=user.idUser,
                    username=user.username,
                    email=user.email,
                    created_at=user.created_at
                )
            return None
        finally:
            db.close()

# ============================================================================
# CATEGORY RESOLVERS
# ============================================================================

async def get_categories() -> List[Category]:
    """Hent alle kategorier"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run("MATCH (c:Category) RETURN c ORDER BY c.idCategory")
            categories = [Category(
                idCategory=record["c"]["idCategory"],
                name=record["c"]["name"],
                type=record["c"]["type"]
            ) for record in result]
        driver.close()
        return categories
    else:
        db = SessionLocal()
        try:
            categories = db.query(CategoryModel).all()
            return [Category(
                idCategory=c.idCategory,
                name=c.name,
                type=c.type
            ) for c in categories]
        finally:
            db.close()

async def get_category(id: int) -> Optional[Category]:
    """Hent specifik kategori"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run("MATCH (c:Category {idCategory: $id}) RETURN c", id=id)
            record = result.single()
            if record:
                c = record["c"]
                return Category(
                    idCategory=c["idCategory"],
                    name=c["name"],
                    type=c["type"]
                )
        driver.close()
        return None
    else:
        db = SessionLocal()
        try:
            category = db.query(CategoryModel).filter(CategoryModel.idCategory == id).first()
            if category:
                return Category(
                    idCategory=category.idCategory,
                    name=category.name,
                    type=category.type
                )
            return None
        finally:
            db.close()

# ============================================================================
# ACCOUNT RESOLVERS
# ============================================================================

async def get_accounts(user_id: Optional[int] = None) -> List[Account]:
    """Hent konti"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            if user_id:
                query = "MATCH (u:User {idUser: $userId})-[:OWNS]->(a:Account) RETURN a, u ORDER BY a.idAccount"
                result = session.run(query, userId=user_id)
            else:
                query = "MATCH (a:Account) RETURN a ORDER BY a.idAccount"
                result = session.run(query)
            
            accounts = []
            for record in result:
                a = record["a"]
                user = None
                if "u" in record:
                    u = record["u"]
                    user = User(
                        idUser=u["idUser"],
                        username=u["username"],
                        email=u["email"],
                        created_at=datetime.fromisoformat(u["created_at"]) if u.get("created_at") else None
                    )
                accounts.append(Account(
                    idAccount=a["idAccount"],
                    name=a["name"],
                    saldo=a["saldo"],
                    user=user
                ))
        driver.close()
        return accounts
    else:
        db = SessionLocal()
        try:
            query = db.query(AccountModel)
            if user_id:
                query = query.filter(AccountModel.User_idUser == user_id)
            accounts = query.all()
            return [Account(
                idAccount=a.idAccount,
                name=a.name,
                saldo=float(a.saldo) if a.saldo else 0.0,
                user=User(
                    idUser=a.user.idUser,
                    username=a.user.username,
                    email=a.user.email,
                    created_at=a.user.created_at
                ) if a.user else None
            ) for a in accounts]
        finally:
            db.close()

async def get_account(id: int) -> Optional[Account]:
    """Hent specifik konto"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run(
                "MATCH (u:User)-[:OWNS]->(a:Account {idAccount: $id}) RETURN a, u",
                id=id
            )
            record = result.single()
            if record:
                a = record["a"]
                u = record.get("u")
                user = None
                if u:
                    user = User(
                        idUser=u["idUser"],
                        username=u["username"],
                        email=u["email"],
                        created_at=datetime.fromisoformat(u["created_at"]) if u.get("created_at") else None
                    )
                return Account(
                    idAccount=a["idAccount"],
                    name=a["name"],
                    saldo=a["saldo"],
                    user=user
                )
        driver.close()
        return None
    else:
        db = SessionLocal()
        try:
            account = db.query(AccountModel).filter(AccountModel.idAccount == id).first()
            if account:
                return Account(
                    idAccount=account.idAccount,
                    name=account.name,
                    saldo=float(account.saldo) if account.saldo else 0.0,
                    user=User(
                        idUser=account.user.idUser,
                        username=account.user.username,
                        email=account.user.email,
                        created_at=account.user.created_at
                    ) if account.user else None
                )
            return None
        finally:
            db.close()

# ============================================================================
# TRANSACTION RESOLVERS
# ============================================================================

async def get_transactions(filter: Optional[TransactionFilter] = None) -> List[Transaction]:
    """Hent transaktioner med filtrering"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            # Byg Cypher query baseret på filter
            query = "MATCH (a:Account)-[:HAS_TRANSACTION]->(t:Transaction)-[:BELONGS_TO_CATEGORY]->(c:Category)"
            conditions = []
            params = {}
            
            if filter:
                if filter.start_date:
                    conditions.append("t.date >= $start_date")
                    params["start_date"] = filter.start_date.isoformat()
                if filter.end_date:
                    conditions.append("t.date <= $end_date")
                    params["end_date"] = filter.end_date.isoformat()
                if filter.category_id:
                    conditions.append("c.idCategory = $category_id")
                    params["category_id"] = filter.category_id
                if filter.account_id:
                    conditions.append("a.idAccount = $account_id")
                    params["account_id"] = filter.account_id
                if filter.type:
                    conditions.append("t.type = $type")
                    params["type"] = filter.type
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " RETURN t, c, a ORDER BY t.date DESC LIMIT 100"
            
            result = session.run(query, **params)
            transactions = []
            for record in result:
                t = record["t"]
                c = record["c"]
                a = record["a"]
                transactions.append(Transaction(
                    idTransaction=t["idTransaction"],
                    amount=t["amount"],
                    description=t.get("description"),
                    date=datetime.fromisoformat(t["date"]) if t.get("date") else datetime.now(),
                    type=t["type"],
                    category=Category(
                        idCategory=c["idCategory"],
                        name=c["name"],
                        type=c["type"]
                    ),
                    account=Account(
                        idAccount=a["idAccount"],
                        name=a["name"],
                        saldo=a["saldo"]
                    )
                ))
        driver.close()
        return transactions
    else:
        db = SessionLocal()
        try:
            query = db.query(TransactionModel)
            if filter:
                if filter.start_date:
                    query = query.filter(TransactionModel.date >= filter.start_date)
                if filter.end_date:
                    query = query.filter(TransactionModel.date <= filter.end_date)
                if filter.category_id:
                    query = query.filter(TransactionModel.Category_idCategory == filter.category_id)
                if filter.account_id:
                    query = query.filter(TransactionModel.Account_idAccount == filter.account_id)
                if filter.type:
                    query = query.filter(TransactionModel.type == filter.type)
            
            transactions = query.order_by(TransactionModel.date.desc()).limit(100).all()
            return [Transaction(
                idTransaction=t.idTransaction,
                amount=float(t.amount) if t.amount else 0.0,
                description=t.description,
                date=t.date,
                type=t.type,
                category=Category(
                    idCategory=t.category.idCategory,
                    name=t.category.name,
                    type=t.category.type
                ) if t.category else None,
                account=Account(
                    idAccount=t.account.idAccount,
                    name=t.account.name,
                    saldo=float(t.account.saldo) if t.account.saldo else 0.0
                ) if t.account else None
            ) for t in transactions]
        finally:
            db.close()

async def get_transaction(id: int) -> Optional[Transaction]:
    """Hent specifik transaktion"""
    if USE_NEO4J:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run(
                "MATCH (a:Account)-[:HAS_TRANSACTION]->(t:Transaction {idTransaction: $id})-[:BELONGS_TO_CATEGORY]->(c:Category) RETURN t, c, a",
                id=id
            )
            record = result.single()
            if record:
                t = record["t"]
                c = record["c"]
                a = record["a"]
                return Transaction(
                    idTransaction=t["idTransaction"],
                    amount=t["amount"],
                    description=t.get("description"),
                    date=datetime.fromisoformat(t["date"]) if t.get("date") else datetime.now(),
                    type=t["type"],
                    category=Category(
                        idCategory=c["idCategory"],
                        name=c["name"],
                        type=c["type"]
                    ),
                    account=Account(
                        idAccount=a["idAccount"],
                        name=a["name"],
                        saldo=a["saldo"]
                    )
                )
        driver.close()
        return None
    else:
        db = SessionLocal()
        try:
            transaction = db.query(TransactionModel).filter(TransactionModel.idTransaction == id).first()
            if transaction:
                return Transaction(
                    idTransaction=transaction.idTransaction,
                    amount=float(transaction.amount) if transaction.amount else 0.0,
                    description=transaction.description,
                    date=transaction.date,
                    type=transaction.type,
                    category=Category(
                        idCategory=transaction.category.idCategory,
                        name=transaction.category.name,
                        type=transaction.category.type
                    ) if transaction.category else None,
                    account=Account(
                        idAccount=transaction.account.idAccount,
                        name=transaction.account.name,
                        saldo=float(transaction.account.saldo) if transaction.account.saldo else 0.0
                    ) if transaction.account else None
                )
            return None
        finally:
            db.close()

# ============================================================================
# BUDGET RESOLVERS
# ============================================================================

async def get_budgets(account_id: Optional[int] = None) -> List[Budget]:
    """Hent budgetter"""
    db = SessionLocal()
    try:
        query = db.query(BudgetModel)
        if account_id:
            query = query.filter(BudgetModel.Account_idAccount == account_id)
        budgets = query.all()
        return [Budget(
            idBudget=b.idBudget,
            amount=float(b.amount) if b.amount else 0.0,
            budget_date=b.budget_date,
            account=Account(
                idAccount=b.account.idAccount,
                name=b.account.name,
                saldo=float(b.account.saldo) if b.account.saldo else 0.0
            ) if b.account else None,
            categories=[Category(
                idCategory=c.idCategory,
                name=c.name,
                type=c.type
            ) for c in b.categories] if hasattr(b, 'categories') and b.categories else None
        ) for b in budgets]
    finally:
        db.close()

# ============================================================================
# GOAL RESOLVERS
# ============================================================================

async def get_goals(account_id: Optional[int] = None) -> List[Goal]:
    """Hent mål"""
    db = SessionLocal()
    try:
        query = db.query(GoalModel)
        if account_id:
            query = query.filter(GoalModel.Account_idAccount == account_id)
        goals = query.all()
        return [Goal(
            idGoal=g.idGoal,
            name=g.name,
            target_amount=float(g.target_amount) if g.target_amount else None,
            current_amount=float(g.current_amount) if g.current_amount else None,
            target_date=g.target_date,
            status=g.status,
            account=Account(
                idAccount=g.account.idAccount,
                name=g.account.name,
                saldo=float(g.account.saldo) if g.account.saldo else 0.0
            ) if g.account else None
        ) for g in goals]
    finally:
        db.close()

# ============================================================================
# MUTATION RESOLVERS
# ============================================================================

async def create_transaction(input: TransactionCreate) -> Transaction:
    """Opret ny transaktion"""
    db = SessionLocal()
    try:
        transaction = TransactionModel(
            amount=Decimal(str(input.amount)),
            description=input.description,
            date=input.date,
            type=input.type,
            Category_idCategory=input.category_id,
            Account_idAccount=input.account_id
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # Hent med relationships
        return await get_transaction(transaction.idTransaction)
    finally:
        db.close()

async def update_transaction(id: int, input: TransactionCreate) -> Optional[Transaction]:
    """Opdater transaktion"""
    db = SessionLocal()
    try:
        transaction = db.query(TransactionModel).filter(TransactionModel.idTransaction == id).first()
        if not transaction:
            return None
        
        transaction.amount = Decimal(str(input.amount))
        transaction.description = input.description
        transaction.date = input.date
        transaction.type = input.type
        transaction.Category_idCategory = input.category_id
        transaction.Account_idAccount = input.account_id
        
        db.commit()
        db.refresh(transaction)
        
        return await get_transaction(id)
    finally:
        db.close()

async def delete_transaction(id: int) -> bool:
    """Slet transaktion"""
    db = SessionLocal()
    try:
        transaction = db.query(TransactionModel).filter(TransactionModel.idTransaction == id).first()
        if not transaction:
            return False
        
        db.delete(transaction)
        db.commit()
        return True
    finally:
        db.close()

