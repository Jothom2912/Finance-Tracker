# backend/migrate_to_elasticsearch.py
from elasticsearch import Elasticsearch
from backend.database import SessionLocal, Transaction, Category
import json
from datetime import datetime

# Elasticsearch client
es = Elasticsearch(["http://localhost:9200"])

def migrate_transactions_to_elasticsearch():
    """
    Migrerer alle transaktioner fra MySQL til Elasticsearch.
    """
    db = SessionLocal()
    try:
        # Test forbindelse
        print("Tester Elasticsearch forbindelse...")
        health = es.cluster.health()
        print(f"✓ Elasticsearch status: {health['status']}")
        
        # Opret index med mapping
        index_name = "transactions"
        
        # Slet eksisterende index hvis den findes
        if es.indices.exists(index=index_name):
            es.indices.delete(index=index_name)
            print(f"Slettet eksisterende index: {index_name}")
        
        # Definer mapping for transaktioner
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "integer"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "amount": {"type": "float"},
                    "date": {"type": "date", "format": "yyyy-MM-dd"},
                    "type": {"type": "keyword"},  # expense or income
                    "category_id": {"type": "integer"},
                    "category_name": {"type": "keyword"},
                    "balance_after": {"type": "float"},
                    "currency": {"type": "keyword"},
                    "sender": {"type": "text"},
                    "recipient": {"type": "text"},
                    "name": {"type": "text"},
                    "created_at": {"type": "date"}
                }
            }
        }
        
        # Opret index
        es.indices.create(index=index_name, body=mapping)
        print(f"✓ Oprettet index: {index_name}")
        
        # Hent alle transaktioner fra MySQL
        transactions = db.query(Transaction).all()
        print(f"Migrerer {len(transactions)} transaktioner...")
        
        if len(transactions) == 0:
            print("⚠ Ingen transaktioner at migrere")
            return
        
        # Bulk insert transaktioner
        bulk_data = []
        for transaction in transactions:
            try:
                # Hent kategorinavn
                category = db.query(Category).filter(Category.id == transaction.category_id).first()
                category_name = category.name if category else "Ukendt"
                
                doc = {
                    "id": transaction.id,
                    "description": transaction.description or "",
                    "amount": float(transaction.amount) if transaction.amount else 0.0,
                    "date": transaction.date.isoformat() if transaction.date else None,
                    "type": transaction.type.value if transaction.type else "expense",
                    "category_id": transaction.category_id or 0,
                    "category_name": category_name,
                    "balance_after": float(transaction.balance_after) if transaction.balance_after else None,
                    "currency": transaction.currency or "DKK",
                    "sender": transaction.sender or "",
                    "recipient": transaction.recipient or "",
                    "name": transaction.name or "",
                    "created_at": datetime.now().isoformat()
                }
                
                # Tilføj til bulk-request
                bulk_data.append({"index": {"_index": index_name, "_id": transaction.id}})
                bulk_data.append(doc)
            except Exception as e:
                print(f"⚠ Fejl ved transaktion {transaction.id}: {e}")
                continue
        
        # Udfør bulk insert
        if bulk_data:
            response = es.bulk(body=bulk_data)
            if response.get('errors'):
                print(f"⚠ Nogle dokumenter fejlede:")
                for item in response.get('items', []):
                    if 'error' in item.get('index', {}):
                        print(f"  - {item['index']['error']}")
            else:
                print(f"✓ Succesfuldt migreret {len(transactions)} transaktioner til Elasticsearch")
        else:
            print("Ingen transaktioner at migrere")
        
        # Refresh index
        es.indices.refresh(index=index_name)
        
        # Vis statistik
        count = es.count(index=index_name)
        print(f"Total dokumenter i Elasticsearch: {count['count']}")
        
    except Exception as e:
        print(f"✗ Fejl ved migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("Starter migration af transaktioner til Elasticsearch...")
    migrate_transactions_to_elasticsearch()
    print("Migration fuldført!")
