# backend/database/__init__.py
"""
Database connections for all database types
"""

# MySQL exports (primary)
from backend.database.mysql import (
    get_db,
    Base,
    engine,
    SessionLocal,
    create_db_tables,
    test_database_connection,
    drop_all_tables
)

# Elasticsearch exports - Lazy import for at undgå at hænge ved startup
def get_es_client():
    """Lazy import af Elasticsearch client - kun når den faktisk bruges"""
    from .elasticsearch import get_es_client as _get_es_client
    return _get_es_client()

# Neo4j exports - Lazy import for at undgå at hænge ved startup
def get_neo4j_driver():
    """Lazy import af Neo4j driver - kun når den faktisk bruges"""
    from .neo4j import get_neo4j_driver as _get_neo4j_driver
    return _get_neo4j_driver()

__all__ = [
    "get_db",
    "Base", 
    "engine",
    "SessionLocal",
    "create_db_tables",
    "test_database_connection",
    "drop_all_tables",
    "get_es_client",  # Lazy import - virker nu
    "get_neo4j_driver"  # Lazy import - virker nu
]
