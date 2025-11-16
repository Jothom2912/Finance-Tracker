# backend/repository/__init__.py
from backend.config import DatabaseType, ACTIVE_DB
from backend.repository.base_repository import ITransactionRepository, ICategoryRepository
from backend.repository.mysql_repository import MySQLTransactionRepository, MySQLCategoryRepository
from backend.repository.elasticsearch_repository import ElasticsearchTransactionRepository, ElasticsearchCategoryRepository

def get_transaction_repository() -> ITransactionRepository:
    """Factory function to get the active transaction repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLTransactionRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchTransactionRepository()
    else:
        # Default til MySQL
        return MySQLTransactionRepository()

def get_category_repository() -> ICategoryRepository:
    """Factory function to get the active category repository."""
    if ACTIVE_DB == DatabaseType.MYSQL.value:
        return MySQLCategoryRepository()
    elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
        return ElasticsearchCategoryRepository()
    else:
        # Default til MySQL
        return MySQLCategoryRepository()
