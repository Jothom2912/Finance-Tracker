# backend/repositories/__init__.py
"""
Repository Factory - Vælg hvilken database der skal bruges
"""
from typing import Optional
from sqlalchemy.orm import Session
from backend.config import DatabaseType, ACTIVE_DB
from backend.repositories.base import (
    ITransactionRepository,
    ICategoryRepository,
    IAccountRepository,
    IUserRepository,
    IBudgetRepository,
    IGoalRepository,
    IPlannedTransactionRepository,
    IAccountGroupRepository,
)

# Factory functions - lazy imports for at undgå at importere alle database drivers
# ✅ FIX: Kræv db: Session parameter for MySQL repositories
def get_transaction_repository(db: Optional[Session] = None) -> ITransactionRepository:
    """Factory function to get the active transaction repository.
    
    Args:
        db: Database session (required for MySQL, optional for other DBs)
    """
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLTransactionRepository(db)
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.transaction_repository import ElasticsearchTransactionRepository
        return ElasticsearchTransactionRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.transaction_repository import Neo4jTransactionRepository
        return Neo4jTransactionRepository()
    else:
        # Default til MySQL
        from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLTransactionRepository(db)

def get_category_repository(db: Optional[Session] = None) -> ICategoryRepository:
    """Factory function to get the active category repository.
    
    Args:
        db: Database session (required for MySQL, optional for other DBs)
    """
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.category_repository import MySQLCategoryRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLCategoryRepository(db)
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.category_repository import ElasticsearchCategoryRepository
        return ElasticsearchCategoryRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.category_repository import Neo4jCategoryRepository
        return Neo4jCategoryRepository()
    else:
        from backend.repositories.mysql.category_repository import MySQLCategoryRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLCategoryRepository(db)

def get_account_repository(db: Optional[Session] = None) -> IAccountRepository:
    """Factory function to get the active account repository.
    
    Args:
        db: Database session (required for MySQL, optional for other DBs)
    """
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.account_repository import MySQLAccountRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLAccountRepository(db)
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.account_repository import ElasticsearchAccountRepository
        return ElasticsearchAccountRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.account_repository import Neo4jAccountRepository
        return Neo4jAccountRepository()
    else:
        from backend.repositories.mysql.account_repository import MySQLAccountRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLAccountRepository(db)

def get_user_repository(db: Optional[Session] = None) -> IUserRepository:
    """Factory function to get the active user repository.
    
    Args:
        db: Database session (required for MySQL, optional for other DBs)
    """
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.user_repository import MySQLUserRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLUserRepository(db)
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.user_repository import ElasticsearchUserRepository
        return ElasticsearchUserRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.user_repository import Neo4jUserRepository
        return Neo4jUserRepository()
    else:
        from backend.repositories.mysql.user_repository import MySQLUserRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLUserRepository(db)

def get_budget_repository(db: Optional[Session] = None) -> IBudgetRepository:
    """Factory function to get the active budget repository.
    
    Args:
        db: Database session (required for MySQL, optional for other DBs)
    """
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLBudgetRepository(db)
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.budget_repository import ElasticsearchBudgetRepository
        return ElasticsearchBudgetRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.budget_repository import Neo4jBudgetRepository
        return Neo4jBudgetRepository()
    else:
        from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLBudgetRepository(db)

def get_goal_repository(db: Optional[Session] = None) -> IGoalRepository:
    """Factory function to get the active goal repository.
    
    Args:
        db: Database session (required for MySQL, optional for other DBs)
    """
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        from backend.repositories.mysql.goal_repository import MySQLGoalRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLGoalRepository(db)
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        from backend.repositories.elasticsearch.goal_repository import ElasticsearchGoalRepository
        return ElasticsearchGoalRepository()
    elif ACTIVE_DB == DatabaseType.NEO4J.value:
        from backend.repositories.neo4j.goal_repository import Neo4jGoalRepository
        return Neo4jGoalRepository()
    else:
        from backend.repositories.mysql.goal_repository import MySQLGoalRepository
        if db is None:
            raise ValueError("db: Session parameter is required for MySQL repositories")
        return MySQLGoalRepository(db)

def get_planned_transaction_repository(db: Optional[Session] = None) -> IPlannedTransactionRepository:
    """Factory function to get the active planned transaction repository.
    
    Args:
        db: Database session (required for MySQL)
    """
    # Currently only MySQL is supported for planned transactions
    from backend.repositories.mysql.planned_transaction_repository import MySQLPlannedTransactionRepository
    if db is None:
        raise ValueError("db: Session parameter is required for MySQL repositories")
    return MySQLPlannedTransactionRepository(db)

def get_account_group_repository(db: Optional[Session] = None) -> IAccountGroupRepository:
    """Factory function to get the active account group repository.
    
    Args:
        db: Database session (required for MySQL)
    """
    # Currently only MySQL is supported for account groups
    from backend.repositories.mysql.account_group_repository import MySQLAccountGroupRepository
    if db is None:
        raise ValueError("db: Session parameter is required for MySQL repositories")
    return MySQLAccountGroupRepository(db)
