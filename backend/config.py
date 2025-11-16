# backend/config.py
import os
from enum import Enum

class DatabaseType(Enum):
    MYSQL = "mysql"
    ELASTICSEARCH = "elasticsearch"
    HYBRID = "hybrid"  # MySQL for writes, ES for reads

# Læs fra environment eller default til MySQL
ACTIVE_DB = os.getenv("ACTIVE_DB", DatabaseType.MYSQL.value)
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
SYNC_TO_ELASTICSEARCH = os.getenv("SYNC_TO_ELASTICSEARCH", "true").lower() == "true"

print(f"✓ Active Database: {ACTIVE_DB}")
print(f"✓ Elasticsearch Host: {ELASTICSEARCH_HOST}")
print(f"✓ Sync to Elasticsearch: {SYNC_TO_ELASTICSEARCH}")
