#!/usr/bin/env python3
"""
Import data from JSON dumps to Elasticsearch
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elasticsearch import Elasticsearch
import json
from backend.database.elasticsearch import get_es_client

DUMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dumps", "elasticsearch")

# Index mappings (from migrations)
INDEX_MAPPINGS = {
    "transactions": {
        "mappings": {
            "properties": {
                "idTransaction": {"type": "integer"},
                "amount": {"type": "float"},
                "description": {"type": "text"},
                "date": {"type": "date"},
                "type": {"type": "keyword"},
                "Category_idCategory": {"type": "integer"},
                "Account_idAccount": {"type": "integer"}
            }
        }
    },
    "categories": {
        "mappings": {
            "properties": {
                "idCategory": {"type": "integer"},
                "name": {"type": "keyword"},
                "type": {"type": "keyword"},
                "description": {"type": "text"}
            }
        }
    },
    "accounts": {
        "mappings": {
            "properties": {
                "idAccount": {"type": "integer"},
                "name": {"type": "text"},
                "saldo": {"type": "float"},
                "User_idUser": {"type": "integer"}
            }
        }
    },
    "users": {
        "mappings": {
            "properties": {
                "idUser": {"type": "integer"},
                "username": {"type": "keyword"},
                "email": {"type": "keyword"},
                "created_at": {"type": "date"}
            }
        }
    },
    "budgets": {
        "mappings": {
            "properties": {
                "idBudget": {"type": "integer"},
                "amount": {"type": "float"},
                "budget_date": {"type": "date"},
                "Account_idAccount": {"type": "integer"}
            }
        }
    },
    "goals": {
        "mappings": {
            "properties": {
                "idGoal": {"type": "integer"},
                "name": {"type": "text"},
                "target_amount": {"type": "float"},
                "current_amount": {"type": "float"},
                "target_date": {"type": "date"},
                "status": {"type": "keyword"},
                "Account_idAccount": {"type": "integer"}
            }
        }
    }
}

def load_elasticsearch():
    """Import all JSON dumps to Elasticsearch"""
    es = get_es_client()
    
    print("=" * 60)
    print("📥 Elasticsearch Load Script")
    print("=" * 60)
    
    # Test connection
    if not es.ping():
        print("❌ Cannot connect to Elasticsearch!")
        return False
    
    print(f"✅ Connected to Elasticsearch")
    print(f"📁 Dump directory: {DUMP_DIR}\n")
    
    if not os.path.exists(DUMP_DIR):
        print(f"❌ Dump directory does not exist: {DUMP_DIR}")
        return False
    
    total_documents = 0
    
    # Get all JSON files
    json_files = [f for f in os.listdir(DUMP_DIR) if f.endswith(".json")]
    
    if not json_files:
        print(f"⚠️  No JSON files found in {DUMP_DIR}")
        return False
    
    for filename in sorted(json_files):
        index_name = filename.replace(".json", "")
        filepath = os.path.join(DUMP_DIR, filename)
        
        try:
            print(f"📥 Loading {index_name}...")
            
            # Read dump file
            with open(filepath, "r", encoding="utf-8") as f:
                documents = json.load(f)
            
            if not documents:
                print(f"⚠️  No documents in {filename}, skipping...")
                continue
            
            # Delete existing index if it exists
            if es.indices.exists(index=index_name):
                print(f"🗑️  Deleting existing index '{index_name}'...")
                es.indices.delete(index=index_name)
            
            # Create index with mapping
            if index_name in INDEX_MAPPINGS:
                es.indices.create(index=index_name, body=INDEX_MAPPINGS[index_name])
                print(f"✅ Created index '{index_name}' with mapping")
            else:
                es.indices.create(index=index_name)
                print(f"✅ Created index '{index_name}' (no mapping)")
            
            # Bulk insert
            bulk_data = []
            for doc in documents:
                # Use idTransaction, idCategory, etc. as document ID
                doc_id = None
                if "idTransaction" in doc:
                    doc_id = doc["idTransaction"]
                elif "idCategory" in doc:
                    doc_id = doc["idCategory"]
                elif "idAccount" in doc:
                    doc_id = doc["idAccount"]
                elif "idUser" in doc:
                    doc_id = doc["idUser"]
                elif "idBudget" in doc:
                    doc_id = doc["idBudget"]
                elif "idGoal" in doc:
                    doc_id = doc["idGoal"]
                
                bulk_data.append({
                    "index": {
                        "_index": index_name,
                        "_id": doc_id
                    }
                })
                bulk_data.append(doc)
            
            if bulk_data:
                # Execute bulk insert
                response = es.bulk(body=bulk_data, refresh=True)
                
                # Check for errors
                if response.get("errors"):
                    errors = [item for item in response["items"] if "error" in item.get("index", {})]
                    if errors:
                        print(f"⚠️  Some documents failed to load: {len(errors)} errors")
                        for error in errors[:5]:  # Show first 5 errors
                            print(f"   Error: {error.get('index', {}).get('error', {})}")
                else:
                    print(f"✅ Loaded {len(documents)} documents to {index_name}")
                    total_documents += len(documents)
            
        except Exception as e:
            print(f"❌ Error loading {filename}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "=" * 60)
    print(f"✅ Load complete! Total documents: {total_documents}")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = load_elasticsearch()
    sys.exit(0 if success else 1)

