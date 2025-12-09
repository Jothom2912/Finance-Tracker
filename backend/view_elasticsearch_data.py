# backend/view_elasticsearch_data.py
"""
Script til at se data i Elasticsearch i tabelformat
"""
from elasticsearch import Elasticsearch
from backend.config import ELASTICSEARCH_HOST
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False
import sys

es = Elasticsearch([ELASTICSEARCH_HOST])

def view_indices():
    """Vis alle indices"""
    print("=" * 60)
    print("📋 ELASTICSEARCH INDICES")
    print("=" * 60)
    
    indices = es.indices.get_alias(index="*")
    for index_name in sorted(indices.keys()):
        count = es.count(index=index_name)['count']
        print(f"  {index_name}: {count} dokumenter")

def view_transactions(limit=10):
    """Vis transaktioner i tabelformat"""
    print("\n" + "=" * 60)
    print(f"💰 TRANSACTIONS (første {limit})")
    print("=" * 60)
    
    result = es.search(
        index="transactions",
        body={"query": {"match_all": {}}, "size": limit, "sort": [{"date": "desc"}]}
    )
    
    if result['hits']['total']['value'] == 0:
        print("  ⚠ Ingen transaktioner fundet")
        return
    
    rows = []
    for hit in result['hits']['hits']:
        doc = hit['_source']
        rows.append([
            doc.get('idTransaction', 'N/A'),
            doc.get('date', 'N/A')[:10] if doc.get('date') else 'N/A',
            doc.get('description', 'N/A')[:30],
            f"{doc.get('amount', 0):.2f}",
            doc.get('type', 'N/A'),
            doc.get('category_name', 'N/A'),
            doc.get('account_name', 'N/A')
        ])
    
    headers = ["ID", "Date", "Description", "Amount", "Type", "Category", "Account"]
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        # Simple tabel uden tabulate
        print(f"  {' | '.join(headers)}")
        print("  " + "-" * 80)
        for row in rows:
            print(f"  {' | '.join(str(x) for x in row)}")

def view_categories():
    """Vis kategorier"""
    print("\n" + "=" * 60)
    print("📁 CATEGORIES")
    print("=" * 60)
    
    result = es.search(
        index="categories",
        body={"query": {"match_all": {}}, "size": 100}
    )
    
    if result['hits']['total']['value'] == 0:
        print("  ⚠ Ingen kategorier fundet")
        return
    
    rows = []
    for hit in result['hits']['hits']:
        doc = hit['_source']
        rows.append([
            doc.get('idCategory', 'N/A'),
            doc.get('name', 'N/A'),
            doc.get('type', 'N/A')
        ])
    
    headers = ["ID", "Name", "Type"]
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print(f"  {' | '.join(headers)}")
        print("  " + "-" * 50)
        for row in rows:
            print(f"  {' | '.join(str(x) for x in row)}")

def view_accounts():
    """Vis konti"""
    print("\n" + "=" * 60)
    print("💳 ACCOUNTS")
    print("=" * 60)
    
    result = es.search(
        index="accounts",
        body={"query": {"match_all": {}}, "size": 100}
    )
    
    if result['hits']['total']['value'] == 0:
        print("  ⚠ Ingen konti fundet")
        return
    
    rows = []
    for hit in result['hits']['hits']:
        doc = hit['_source']
        rows.append([
            doc.get('idAccount', 'N/A'),
            doc.get('name', 'N/A'),
            f"{doc.get('saldo', 0):.2f}",
            doc.get('username', 'N/A')
        ])
    
    headers = ["ID", "Name", "Saldo", "User"]
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print(f"  {' | '.join(headers)}")
        print("  " + "-" * 50)
        for row in rows:
            print(f"  {' | '.join(str(x) for x in row)}")

def main():
    """Hovedfunktion"""
    try:
        # Test forbindelse
        health = es.cluster.health()
        print(f"✓ Elasticsearch status: {health['status']}")
        print(f"✓ Elasticsearch host: {ELASTICSEARCH_HOST}\n")
    except Exception as e:
        print(f"✗ Kan ikke forbinde til Elasticsearch: {e}")
        print(f"💡 Sørg for at Elasticsearch kører på {ELASTICSEARCH_HOST}")
        sys.exit(1)
    
    # Vis data
    view_indices()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "transactions":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            view_transactions(limit)
        elif sys.argv[1] == "categories":
            view_categories()
        elif sys.argv[1] == "accounts":
            view_accounts()
    else:
        # Vis alt
        view_transactions(10)
        view_categories()
        view_accounts()
    
    print("\n" + "=" * 60)
    print("💡 Tip: Brug Kibana på http://localhost:5601 for bedre visualisering")
    print("=" * 60)

if __name__ == "__main__":
    main()

