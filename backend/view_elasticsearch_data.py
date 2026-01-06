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

# Elasticsearch client - eksplicit brug API version 8 for kompatibilitet med ES 8.11.0
es = Elasticsearch(
    [ELASTICSEARCH_HOST],
    request_timeout=30,
    max_retries=3,
    retry_on_timeout=True,
    headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8", "Content-Type": "application/vnd.elasticsearch+json; compatible-with=8"}
)

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

def view_overview():
    """Vis et komplet overview over al data med statistikker og diagram"""
    print("\n" + "=" * 80)
    print("📊 ELASTICSEARCH DATA OVERVIEW")
    print("=" * 80)
    
    # Hent alle indices
    indices_info = {}
    all_indices = ["users", "accounts", "categories", "transactions", "budgets", "goals", "account_groups", "planned_transactions"]
    
    total_docs = 0
    for index_name in all_indices:
        try:
            count = es.count(index=index_name)['count']
            indices_info[index_name] = count
            total_docs += count
        except:
            indices_info[index_name] = 0
    
    # Vis index statistikker
    print("\n📋 INDICES OVERVIEW:")
    print("-" * 80)
    
    if HAS_TABULATE:
        rows = []
        for index_name, count in sorted(indices_info.items()):
            percentage = (count / total_docs * 100) if total_docs > 0 else 0
            rows.append([
                index_name,
                count,
                f"{percentage:.1f}%",
                "█" * min(int(percentage / 2), 40)  # Bar chart
            ])
        print(tabulate(rows, headers=["Index", "Documents", "Percentage", "Visual"], tablefmt="grid"))
    else:
        print(f"{'Index':<25} {'Documents':<12} {'Percentage':<12} {'Visual'}")
        print("-" * 80)
        for index_name, count in sorted(indices_info.items()):
            percentage = (count / total_docs * 100) if total_docs > 0 else 0
            bar = "█" * min(int(percentage / 2), 40)
            print(f"{index_name:<25} {count:<12} {percentage:>6.1f}%     {bar}")
    
    print(f"\n📊 Total dokumenter: {total_docs}")
    
    # Transaktions statistikker
    if indices_info.get("transactions", 0) > 0:
        print("\n💰 TRANSACTION STATISTICS:")
        print("-" * 80)
        
        try:
            # Aggregation for income vs expenses
            agg_result = es.search(
                index="transactions",
                body={
                    "size": 0,
                    "aggs": {
                        "by_type": {
                            "terms": {"field": "type", "size": 10},
                            "aggs": {
                                "total_amount": {"sum": {"field": "amount"}},
                                "count": {"value_count": {"field": "amount"}}
                            }
                        },
                        "total_income": {
                            "filter": {"term": {"type": "income"}},
                            "aggs": {"sum": {"sum": {"field": "amount"}}}
                        },
                        "total_expenses": {
                            "filter": {"term": {"type": "expense"}},
                            "aggs": {"sum": {"sum": {"field": "amount"}}}
                        }
                    }
                }
            )
            
            total_income = agg_result['aggregations']['total_income']['sum']['value'] or 0
            total_expenses = abs(agg_result['aggregations']['total_expenses']['sum']['value'] or 0)
            net = total_income - total_expenses
            
            print(f"  Total Income:     {total_income:>15,.2f} DKK")
            print(f"  Total Expenses:   {total_expenses:>15,.2f} DKK")
            print(f"  Net Change:       {net:>15,.2f} DKK")
            
            # Top kategorier
            cat_agg = es.search(
                index="transactions",
                body={
                    "size": 0,
                    "aggs": {
                        "top_categories": {
                            "terms": {"field": "category_name.keyword", "size": 5},
                            "aggs": {"total": {"sum": {"field": "amount"}}}
                        }
                    }
                }
            )
            
            if cat_agg['aggregations']['top_categories']['buckets']:
                print(f"\n  Top 5 Categories by Amount:")
                for bucket in cat_agg['aggregations']['top_categories']['buckets']:
                    print(f"    {bucket['key']:<30} {abs(bucket['total']['value']):>12,.2f} DKK")
        except Exception as e:
            print(f"  ⚠ Kunne ikke hente transaktions statistikker: {e}")
    
    # Account statistikker
    if indices_info.get("accounts", 0) > 0:
        print("\n💳 ACCOUNT STATISTICS:")
        print("-" * 80)
        try:
            acc_result = es.search(
                index="accounts",
                body={
                    "size": 0,
                    "aggs": {
                        "total_saldo": {"sum": {"field": "saldo"}},
                        "avg_saldo": {"avg": {"field": "saldo"}},
                        "min_saldo": {"min": {"field": "saldo"}},
                        "max_saldo": {"max": {"field": "saldo"}}
                    }
                }
            )
            
            aggs = acc_result['aggregations']
            print(f"  Total Saldo:      {aggs['total_saldo']['value'] or 0:>15,.2f} DKK")
            print(f"  Average Saldo:    {aggs['avg_saldo']['value'] or 0:>15,.2f} DKK")
            print(f"  Min Saldo:        {aggs['min_saldo']['value'] or 0:>15,.2f} DKK")
            print(f"  Max Saldo:        {aggs['max_saldo']['value'] or 0:>15,.2f} DKK")
        except Exception as e:
            print(f"  ⚠ Kunne ikke hente account statistikker: {e}")
    
    # User statistikker
    if indices_info.get("users", 0) > 0:
        print(f"\n👤 USERS: {indices_info['users']} brugere")
    
    # Category statistikker
    if indices_info.get("categories", 0) > 0:
        print(f"\n📁 CATEGORIES: {indices_info['categories']} kategorier")
        try:
            cat_type_agg = es.search(
                index="categories",
                body={
                    "size": 0,
                    "aggs": {
                        "by_type": {"terms": {"field": "type.keyword", "size": 10}}
                    }
                }
            )
            
            if cat_type_agg['aggregations']['by_type']['buckets']:
                print("  By Type:")
                for bucket in cat_type_agg['aggregations']['by_type']['buckets']:
                    print(f"    {bucket['key']:<20} {bucket['doc_count']:>5} kategorier")
        except:
            pass
    
    # Budget statistikker
    if indices_info.get("budgets", 0) > 0:
        print(f"\n📊 BUDGETS: {indices_info['budgets']} budgetter")
        try:
            budget_agg = es.search(
                index="budgets",
                body={
                    "size": 0,
                    "aggs": {
                        "total_budget": {"sum": {"field": "amount"}},
                        "avg_budget": {"avg": {"field": "amount"}}
                    }
                }
            )
            
            aggs = budget_agg['aggregations']
            print(f"  Total Budget:     {aggs['total_budget']['value'] or 0:>15,.2f} DKK")
            print(f"  Average Budget:   {aggs['avg_budget']['value'] or 0:>15,.2f} DKK")
        except:
            pass
    
    # Goals statistikker
    if indices_info.get("goals", 0) > 0:
        print(f"\n🎯 GOALS: {indices_info['goals']} mål")
        try:
            goal_agg = es.search(
                index="goals",
                body={
                    "size": 0,
                    "aggs": {
                        "total_target": {"sum": {"field": "target_amount"}},
                        "total_current": {"sum": {"field": "current_amount"}},
                        "by_status": {"terms": {"field": "status.keyword", "size": 10}}
                    }
                }
            )
            
            aggs = goal_agg['aggregations']
            total_target = aggs['total_target']['value'] or 0
            total_current = aggs['total_current']['value'] or 0
            progress = (total_current / total_target * 100) if total_target > 0 else 0
            
            print(f"  Total Target:     {total_target:>15,.2f} DKK")
            print(f"  Total Current:    {total_current:>15,.2f} DKK")
            print(f"  Progress:         {progress:>14.1f}%")
            
            if aggs['by_status']['buckets']:
                print("  By Status:")
                for bucket in aggs['by_status']['buckets']:
                    print(f"    {bucket['key']:<20} {bucket['doc_count']:>5} mål")
        except:
            pass
    
    print("\n" + "=" * 80)

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
        if sys.argv[1] == "overview":
            view_overview()
        elif sys.argv[1] == "transactions":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            view_transactions(limit)
        elif sys.argv[1] == "categories":
            view_categories()
        elif sys.argv[1] == "accounts":
            view_accounts()
    else:
        # Vis overview som standard
        view_overview()
        print("\n")
        view_transactions(10)
        view_categories()
        view_accounts()
    
    print("\n" + "=" * 60)
    print("💡 Tip: Brug Kibana på http://localhost:5601 for bedre visualisering")
    print("=" * 60)

if __name__ == "__main__":
    main()

