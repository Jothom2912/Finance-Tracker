# backend/repositories/__init__.py
"""
Repository Factory - Vælg hvilken database der skal bruges
"""
from backend.config import DatabaseType, ACTIVE_DB
from backend.repositories.base import (
    IGroupAccountRepository,
    IPlannedTransaction,
    ITransactionRepository,
    ICategoryRepository,
    IAccountRepository,
    IUserRepository,
    IBudgetRepository,
    IGoalRepository
    
)

# Import alle repository implementations
from backend.repositories.elasticsearch.group_account_repository import ElasticsearchGroupAccountRepository
from backend.repositories.elasticsearch.planned_transaction_repository import ElasticsearchPlannedTransactionRepository
from backend.repositories.mysql.plannedTransaction_repository import MySQLPlannedTransactionRepository
from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository
from backend.repositories.mysql.category_repository import MySQLCategoryRepository
from backend.repositories.mysql.account_repository import MySQLAccountRepository
from backend.repositories.mysql.user_repository import MySQLUserRepository
from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
from backend.repositories.mysql.goal_repository import MySQLGoalRepository
from backend.repositories.mysql.groupAccount_repository import MySQGroupAccountRepository

from backend.repositories.elasticsearch.transaction_repository import ElasticsearchTransactionRepository
from backend.repositories.elasticsearch.category_repository import ElasticsearchCategoryRepository
from backend.repositories.elasticsearch.account_repository import ElasticsearchAccountRepository
from backend.repositories.elasticsearch.user_repository import ElasticsearchUserRepository
from backend.repositories.elasticsearch.budget_repository import ElasticsearchBudgetRepository
from backend.repositories.elasticsearch.goal_repository import ElasticsearchGoalRepository

from backend.repositories.neo4j.group_account_repository import Neo4jGroupAccountRepository
from backend.repositories.neo4j.plannedTransaction_Repository import Neo4jPlannedTransactionRepository
from backend.repositories.neo4j.transaction_repository import Neo4jTransactionRepository
from backend.repositories.neo4j.category_repository import Neo4jCategoryRepository
from backend.repositories.neo4j.account_repository import Neo4jAccountRepository
from backend.repositories.neo4j.user_repository import Neo4jUserRepository
from backend.repositories.neo4j.budget_repository import Neo4jBudgetRepository
from backend.repositories.neo4j.goal_repository import Neo4jGoalRepository

# Factory functions
def get_transaction_repository() -> ITransactionRepository:
    """Factory function to get the active transaction repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLTransactionRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchTransactionRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jTransactionRepository()
    else:
        # Default til MySQL
        return MySQLTransactionRepository()

def get_category_repository() -> ICategoryRepository:
    """Factory function to get the active category repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLCategoryRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchCategoryRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jCategoryRepository()
    else:
        return MySQLCategoryRepository()

def get_account_repository() -> IAccountRepository:
    """Factory function to get the active account repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLAccountRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchAccountRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jAccountRepository()
    else:
        return MySQLAccountRepository()

def get_user_repository() -> IUserRepository:
    """Factory function to get the active user repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLUserRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchUserRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jUserRepository()
    else:
        return MySQLUserRepository()

def get_budget_repository() -> IBudgetRepository:
    """Factory function to get the active budget repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLBudgetRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchBudgetRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jBudgetRepository()
    else:
        return MySQLBudgetRepository()

def get_goal_repository() -> IGoalRepository:
    """Factory function to get the active goal repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLGoalRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchGoalRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jGoalRepository()
    else:
        return MySQLGoalRepository()

def get_planned_transaction_repository() -> IPlannedTransaction:
    """Factory function to get the active planned transaction repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLPlannedTransactionRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchPlannedTransactionRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jPlannedTransactionRepository()
    else:
        return MySQLPlannedTransactionRepository()

def get_account_group_repository() -> IGroupAccountRepository:
    """Factory function to get the active account group repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQGroupAccountRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchGroupAccountRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        return Neo4jGroupAccountRepository()
    else:
        return MySQGroupAccountRepository()
