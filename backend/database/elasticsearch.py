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
    
    Note: Elasticsearch 9.x client defaults to API version 9, but server may only support 7 or 8.
    This is handled by catching version errors and retrying with proper headers if needed.
    """
    global _es_client
    if _es_client is None:
        from backend.config import ELASTICSEARCH_HOST
        # Tvinger API version 8 headers for at undgå version 9 fejl med ES 8.11.0 server
        _es_client = Elasticsearch(
            [ELASTICSEARCH_HOST],
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True,
            headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8", "Content-Type": "application/vnd.elasticsearch+json; compatible-with=8"}
        )
    return _es_client

