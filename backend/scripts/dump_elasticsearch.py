#!/usr/bin/env python3
"""
Export Elasticsearch indices to JSON files
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elasticsearch import Elasticsearch
import json
from backend.database.elasticsearch import get_es_client

INDICES = ["transactions", "categories", "accounts", "users", "budgets", "goals"]
DUMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dumps", "elasticsearch")

def dump_elasticsearch():
    """Export all indices to JSON files"""
    es = get_es_client()
    
    # Create dump directory
    os.makedirs(DUMP_DIR, exist_ok=True)
    
    print("=" * 60)
    print("📦 Elasticsearch Dump Script")
    print("=" * 60)
    
    # Test connection
    if not es.ping():
        print("❌ Cannot connect to Elasticsearch!")
        return False
    
    print(f"✅ Connected to Elasticsearch")
    print(f"📁 Dump directory: {DUMP_DIR}\n")
    
    total_documents = 0
    
    for index in INDICES:
        try:
            # Check if index exists
            if not es.indices.exists(index=index):
                print(f"⚠️  Index '{index}' does not exist, skipping...")
                continue
            
            print(f"📦 Dumping {index}...")
            
            # Get all documents (scroll for large datasets)
            documents = []
            scroll_size = 1000
            scroll_timeout = "2m"
            
            # Initial search
            result = es.search(
                index=index,
                body={"query": {"match_all": {}}},
                scroll=scroll_timeout,
                size=scroll_size
            )
            
            scroll_id = result.get("_scroll_id")
            hits = result["hits"]["hits"]
            
            # Collect first batch
            documents.extend([hit["_source"] for hit in hits])
            
            # Scroll through remaining documents
            while len(hits) > 0:
                result = es.scroll(
                    scroll_id=scroll_id,
                    scroll=scroll_timeout
                )
                scroll_id = result.get("_scroll_id")
                hits = result["hits"]["hits"]
                documents.extend([hit["_source"] for hit in hits])
            
            # Clear scroll
            if scroll_id:
                es.clear_scroll(scroll_id=scroll_id)
            
            # Get index mapping (schema/structure)
            try:
                mapping = es.indices.get_mapping(index=index)
                index_mapping = mapping[index].get("mappings", {})
            except Exception as e:
                print(f"⚠️  Could not get mapping for {index}: {str(e)}")
                index_mapping = {}
            
            # Save documents to JSON file
            output_file = os.path.join(DUMP_DIR, f"{index}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(documents, f, indent=2, default=str, ensure_ascii=False)
            
            # Save mapping to separate file
            if index_mapping:
                mapping_file = os.path.join(DUMP_DIR, f"{index}.mapping.json")
                with open(mapping_file, "w", encoding="utf-8") as f:
                    json.dump({"mappings": index_mapping}, f, indent=2, ensure_ascii=False)
                print(f"✅ Saved {len(documents)} documents + mapping to {index}.json")
            else:
                print(f"✅ Saved {len(documents)} documents to {index}.json")
            
            total_documents += len(documents)
            
        except Exception as e:
            print(f"❌ Error dumping {index}: {str(e)}")
            continue
    
    print("\n" + "=" * 60)
    print(f"✅ Dump complete! Total documents: {total_documents}")
    print(f"📁 Files saved to: {DUMP_DIR}")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = dump_elasticsearch()
    sys.exit(0 if success else 1)

