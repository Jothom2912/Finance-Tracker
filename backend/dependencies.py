# backend/dependencies.py
"""
FastAPI dependency injection wiring.

This module creates service instances with constructor-injected
dependencies for FastAPI's Depends().

All active domains use hexagonal architecture, including analytics.

Usage in routes:
    from backend.dependencies import get_transaction_service

    @router.get("/")
    def list_items(service: TransactionService = Depends(get_transaction_service)):
        return service.list_transactions(account_id=1)
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.config import ANALYTICS_DB, DatabaseType
from backend.database.mysql import get_db

# Hexagonal User domain
from backend.user.application.service import UserService as HexUserService
from backend.user.adapters.outbound.mysql_user_repository import (
    MySQLUserRepository as HexMySQLUserRepository,
)
from backend.user.adapters.outbound.account_adapter import (
    MySQLAccountAdapter as UserAccountAdapter,
)

# Hexagonal Goal domain
from backend.goal.application.service import GoalService as HexGoalService
from backend.goal.adapters.outbound.mysql_goal_repository import (
    MySQLGoalRepository as HexMySQLGoalRepository,
)
from backend.goal.adapters.outbound.account_adapter import (
    MySQLAccountAdapter as GoalAccountAdapter,
)

# Hexagonal Account domain
from backend.account.application.service import AccountService as HexAccountService
from backend.account.adapters.outbound.mysql_account_repository import (
    MySQLAccountRepository as HexMySQLAccountRepository,
)
from backend.account.adapters.outbound.mysql_account_group_repository import (
    MySQLAccountGroupRepository as HexMySQLAccountGroupRepository,
)
from backend.account.adapters.outbound.user_adapter import MySQLUserAdapter

# Hexagonal Transaction domain
from backend.transaction.application.service import TransactionService
from backend.transaction.adapters.outbound.mysql_repository import (
    MySQLTransactionRepository,
    MySQLPlannedTransactionRepository,
)
from backend.transaction.adapters.outbound.mysql_category_adapter import (
    MySQLCategoryAdapter as TransactionCategoryAdapter,
)

# Hexagonal Category domain
from backend.category.application.service import CategoryService
from backend.category.adapters.outbound.mysql_repository import (
    MySQLCategoryRepository as HexMySQLCategoryRepository,
)

# Hexagonal Budget domain
from backend.budget.application.service import BudgetService as HexBudgetService
from backend.budget.adapters.outbound.mysql_repository import (
    MySQLBudgetRepository as HexMySQLBudgetRepository,
)
from backend.budget.adapters.outbound.category_adapter import (
    MySQLCategoryAdapter as BudgetCategoryAdapter,
)

# Hexagonal Analytics domain
from backend.analytics.application.service import AnalyticsService
from backend.analytics.adapters.outbound.mysql_repository import (
    MySQLAnalyticsReadRepository,
)
from backend.analytics.adapters.outbound.elasticsearch_repository import (
    ElasticsearchAnalyticsReadRepository,
)
from backend.analytics.adapters.outbound.neo4j_repository import (
    Neo4jAnalyticsReadRepository,
)


def get_transaction_service(
    db: Session = Depends(get_db),
) -> TransactionService:
    """Create TransactionService with hexagonal architecture repositories."""
    return TransactionService(
        transaction_repo=MySQLTransactionRepository(db),
        category_port=TransactionCategoryAdapter(db),
        planned_transaction_repo=MySQLPlannedTransactionRepository(db),
    )


def get_budget_service(
    db: Session = Depends(get_db),
) -> HexBudgetService:
    """Create hexagonal BudgetService with proper repositories."""
    return HexBudgetService(
        budget_repo=HexMySQLBudgetRepository(db),
        category_port=BudgetCategoryAdapter(db),
    )


def get_analytics_service(
    db: Session = Depends(get_db),
) -> AnalyticsService:
    """Create AnalyticsService with DB-specific read adapter."""
    if ANALYTICS_DB == DatabaseType.ELASTICSEARCH.value:
        return AnalyticsService(read_repo=ElasticsearchAnalyticsReadRepository())
    if ANALYTICS_DB == DatabaseType.NEO4J.value:
        return AnalyticsService(read_repo=Neo4jAnalyticsReadRepository())
    return AnalyticsService(read_repo=MySQLAnalyticsReadRepository(db))


def get_category_service(
    db: Session = Depends(get_db),
) -> CategoryService:
    """Create CategoryService with hexagonal architecture repository."""
    return CategoryService(
        category_repo=HexMySQLCategoryRepository(db),
    )


def get_goal_service(
    db: Session = Depends(get_db),
) -> HexGoalService:
    """Create hexagonal GoalService with proper repositories."""
    return HexGoalService(
        goal_repository=HexMySQLGoalRepository(db),
        account_port=GoalAccountAdapter(db),
    )


def get_account_service(
    db: Session = Depends(get_db),
) -> HexAccountService:
    """Create hexagonal AccountService with proper repositories."""
    return HexAccountService(
        account_repository=HexMySQLAccountRepository(db),
        account_group_repository=HexMySQLAccountGroupRepository(db),
        user_port=MySQLUserAdapter(db),
    )


def get_user_service(
    db: Session = Depends(get_db),
) -> HexUserService:
    """Create hexagonal UserService with proper repositories."""
    return HexUserService(
        user_repository=HexMySQLUserRepository(db),
        account_port=UserAccountAdapter(db),
    )
