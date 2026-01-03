# backend/repositories/__init__.py
"""
Repository Factory - Vælg hvilken database der skal bruges
"""
from backend.config import DatabaseType, ACTIVE_DB
from backend.repositories.base import (
    ITransactionRepository,
    ICategoryRepository,
    IAccountRepository,
    IUserRepository,
    IBudgetRepository,
    IGoalRepository
)

# Factory functions - lazy imports for at undgå at importere alle database drivers
def get_transaction_repository() -> ITransactionRepository:
    """Factory function to get the active transaction repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository
        return MySQLTransactionRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.transaction_repository import ElasticsearchTransactionRepository
        return ElasticsearchTransactionRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.transaction_repository import Neo4jTransactionRepository
        return Neo4jTransactionRepository()
    else:
        # Default til MySQL
        from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository
        return MySQLTransactionRepository()

def get_category_repository() -> ICategoryRepository:
    """Factory function to get the active category repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.category_repository import MySQLCategoryRepository
        return MySQLCategoryRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.category_repository import ElasticsearchCategoryRepository
        return ElasticsearchCategoryRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.category_repository import Neo4jCategoryRepository
        return Neo4jCategoryRepository()
    else:
        from backend.repositories.mysql.category_repository import MySQLCategoryRepository
        return MySQLCategoryRepository()

def get_account_repository() -> IAccountRepository:
    """Factory function to get the active account repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.account_repository import MySQLAccountRepository
        return MySQLAccountRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.account_repository import ElasticsearchAccountRepository
        return ElasticsearchAccountRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.account_repository import Neo4jAccountRepository
        return Neo4jAccountRepository()
    else:
        from backend.repositories.mysql.account_repository import MySQLAccountRepository
        return MySQLAccountRepository()

def get_user_repository() -> IUserRepository:
    """Factory function to get the active user repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.user_repository import MySQLUserRepository
        return MySQLUserRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.user_repository import ElasticsearchUserRepository
        return ElasticsearchUserRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.user_repository import Neo4jUserRepository
        return Neo4jUserRepository()
    else:
        from backend.repositories.mysql.user_repository import MySQLUserRepository
        return MySQLUserRepository()

def get_budget_repository() -> IBudgetRepository:
    """Factory function to get the active budget repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
        return MySQLBudgetRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.budget_repository import ElasticsearchBudgetRepository
        return ElasticsearchBudgetRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.budget_repository import Neo4jBudgetRepository
        return Neo4jBudgetRepository()
    else:
        from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
        return MySQLBudgetRepository()

def get_goal_repository() -> IGoalRepository:
    """Factory function to get the active goal repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.goal_repository import MySQLGoalRepository
        return MySQLGoalRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.goal_repository import ElasticsearchGoalRepository
        return ElasticsearchGoalRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.goal_repository import Neo4jGoalRepository
        return Neo4jGoalRepository()
    else:
        from backend.repositories.mysql.goal_repository import MySQLGoalRepository
        return MySQLGoalRepository()
