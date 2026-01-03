# backend/config.py
import os
from enum import Enum
from dotenv import load_dotenv

# Load .env fil FØRST
load_dotenv()

class DatabaseType(Enum):
    MYSQL = "mysql"
    ELASTICSEARCH = "elasticsearch"
    NEO4J = "neo4j"
    HYBRID = "hybrid"

# Nu læses værdierne korrekt fra .env
ACTIVE_DB = os.getenv("ACTIVE_DB", DatabaseType.MYSQL.value)
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
SYNC_TO_ELASTICSEARCH = os.getenv("SYNC_TO_ELASTICSEARCH", "true").lower() == "true"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
USE_NEO4J = os.getenv("USE_NEO4J", "false").lower() == "true"

print(f"✓ Active Database: {ACTIVE_DB}")
print(f"✓ Elasticsearch Host: {ELASTICSEARCH_HOST}")
print(f"✓ Sync to Elasticsearch: {SYNC_TO_ELASTICSEARCH}")
print(f"✓ Neo4j URI: {NEO4J_URI}")
print(f"✓ Use Neo4j for GraphQL: {USE_NEO4J}")