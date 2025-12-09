# backend/database/neo4j.py
"""
Neo4j Database Connection
"""
from neo4j import GraphDatabase
from typing import Optional

# Singleton Neo4j driver instance
_neo4j_driver = None

def get_neo4j_driver():
    """
    Get or create Neo4j driver instance.
    Uses singleton pattern to reuse connection.
    
    Note: Connection is only created when this function is called, not at import time.
    """
    global _neo4j_driver
    if _neo4j_driver is None:
        from backend.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        _neo4j_driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
    return _neo4j_driver

def close_neo4j_driver():
    """Close Neo4j driver connection."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        _neo4j_driver.close()
        _neo4j_driver = None

