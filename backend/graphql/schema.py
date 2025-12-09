# backend/graphql/schema.py
"""
GraphQL schema definitions for Finance Tracker
Bruger Strawberry GraphQL
"""
import strawberry
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

# ============================================================================
# GRAPHQL TYPES
# ============================================================================

@strawberry.type
class User:
    idUser: int
    username: str
    email: str
    created_at: Optional[datetime] = None

@strawberry.type
class Category:
    idCategory: int
    name: str
    type: str  # 'income' or 'expense'

@strawberry.type
class Account:
    idAccount: int
    name: str
    saldo: float
    user: Optional[User] = None
    transactions: Optional[List['Transaction']] = None

@strawberry.type
class Transaction:
    idTransaction: int
    amount: float
    description: Optional[str] = None
    date: datetime
    type: str  # 'income' or 'expense'
    category: Optional[Category] = None
    account: Optional[Account] = None

@strawberry.type
class Budget:
    idBudget: int
    amount: float
    budget_date: Optional[date] = None
    account: Optional[Account] = None
    categories: Optional[List[Category]] = None

@strawberry.type
class Goal:
    idGoal: int
    name: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    target_date: Optional[date] = None
    status: Optional[str] = None
    account: Optional[Account] = None

# ============================================================================
# INPUT TYPES
# ============================================================================

@strawberry.input
class TransactionFilter:
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    type: Optional[str] = None  # 'income' or 'expense'

@strawberry.input
class TransactionCreate:
    amount: float
    description: Optional[str] = None
    date: datetime
    type: str
    category_id: int
    account_id: int

# ============================================================================
# QUERY TYPE
# ============================================================================

@strawberry.type
class Query:
    @strawberry.field
    async def users(self) -> List[User]:
        """Hent alle brugere"""
        from backend.graphql.resolvers import get_users
        return await get_users()
    
    @strawberry.field
    async def user(self, id: int) -> Optional[User]:
        """Hent specifik bruger"""
        from backend.graphql.resolvers import get_user
        return await get_user(id)
    
    @strawberry.field
    async def accounts(self, user_id: Optional[int] = None) -> List[Account]:
        """Hent konti, evt. filtreret på user_id"""
        from backend.graphql.resolvers import get_accounts
        return await get_accounts(user_id)
    
    @strawberry.field
    async def account(self, id: int) -> Optional[Account]:
        """Hent specifik konto"""
        from backend.graphql.resolvers import get_account
        return await get_account(id)
    
    @strawberry.field
    async def categories(self) -> List[Category]:
        """Hent alle kategorier"""
        from backend.graphql.resolvers import get_categories
        return await get_categories()
    
    @strawberry.field
    async def category(self, id: int) -> Optional[Category]:
        """Hent specifik kategori"""
        from backend.graphql.resolvers import get_category
        return await get_category(id)
    
    @strawberry.field
    async def transactions(self, filter: Optional[TransactionFilter] = None) -> List[Transaction]:
        """Hent transaktioner med filtrering"""
        from backend.graphql.resolvers import get_transactions
        return await get_transactions(filter)
    
    @strawberry.field
    async def transaction(self, id: int) -> Optional[Transaction]:
        """Hent specifik transaktion"""
        from backend.graphql.resolvers import get_transaction
        return await get_transaction(id)
    
    @strawberry.field
    async def budgets(self, account_id: Optional[int] = None) -> List[Budget]:
        """Hent budgetter, evt. filtreret på account_id"""
        from backend.graphql.resolvers import get_budgets
        return await get_budgets(account_id)
    
    @strawberry.field
    async def goals(self, account_id: Optional[int] = None) -> List[Goal]:
        """Hent mål, evt. filtreret på account_id"""
        from backend.graphql.resolvers import get_goals
        return await get_goals(account_id)

# ============================================================================
# MUTATION TYPE
# ============================================================================

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_transaction(self, input: TransactionCreate) -> Transaction:
        """Opret ny transaktion"""
        from backend.graphql.resolvers import create_transaction
        return await create_transaction(input)
    
    @strawberry.mutation
    async def update_transaction(self, id: int, input: TransactionCreate) -> Optional[Transaction]:
        """Opdater transaktion"""
        from backend.graphql.resolvers import update_transaction
        return await update_transaction(id, input)
    
    @strawberry.mutation
    async def delete_transaction(self, id: int) -> bool:
        """Slet transaktion"""
        from backend.graphql.resolvers import delete_transaction
        return await delete_transaction(id)

# ============================================================================
# SCHEMA
# ============================================================================

schema = strawberry.Schema(query=Query, mutation=Mutation)

