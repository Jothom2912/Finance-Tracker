# backend/database/elasticsearch.py
"""
Elasticsearch Connection
"""
from elasticsearch import Elasticsearch
from typing import Optional

# Singleton ES client instance
_es_client: Optional[Elasticsearch] = None

def get_es_client() -> Elasticsearch:
    """
    Get or create Elasticsearch client instance.
    Uses singleton pattern to reuse connection.
    
    Note: Connection is only created when this function is called, not at import time.
    """
    global _es_client
    if _es_client is None:
        from backend.config import ELASTICSEARCH_HOST
        _es_client = Elasticsearch([ELASTICSEARCH_HOST])
    return _es_client

