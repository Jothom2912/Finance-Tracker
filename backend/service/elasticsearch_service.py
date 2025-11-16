# backend/service/elasticsearch_service.py
from elasticsearch import Elasticsearch
from typing import List, Dict, Optional
from datetime import date

es = Elasticsearch(["http://localhost:9200"])

class ElasticsearchService:
    """Service til at arbejde med Elasticsearch transaktioner."""
    
    INDEX_NAME = "transactions"
    
    @staticmethod
    def search_transactions(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Søger efter transaktioner i Elasticsearch.
        """
        query = {
            "bool": {
                "must": []
            }
        }
        
        # Dato-filter
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["gte"] = start_date.isoformat()
            if end_date:
                date_filter["lte"] = end_date.isoformat()
            query["bool"]["must"].append({
                "range": {
                    "date": date_filter
                }
            })
        
        # Kategori-filter
        if category_id:
            query["bool"]["must"].append({
                "term": {
                    "category_id": category_id
                }
            })
        
        # Tekst-søgning
        if search_text:
            query["bool"]["must"].append({
                "multi_match": {
                    "query": search_text,
                    "fields": ["description", "name", "sender", "recipient"]
                }
            })
        
        # Hvis ingen filters, så match alle
        if not query["bool"]["must"]:
            query = {"match_all": {}}
        
        body = {
            "query": query,
            "from": offset,
            "size": limit,
            "sort": [{"date": {"order": "desc"}}]
        }
        
        response = es.search(index=ElasticsearchService.INDEX_NAME, body=body)
        
        # Transformer resultater
        transactions = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            source["id"] = hit["_id"]
            transactions.append(source)
        
        return transactions
    
    @staticmethod
    def get_category_summary(start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict:
        """
        Får en opsummering af udgifter pr. kategori.
        """
        query = {"bool": {"must": []}}
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["gte"] = start_date.isoformat()
            if end_date:
                date_filter["lte"] = end_date.isoformat()
            query["bool"]["must"].append({
                "range": {"date": date_filter}
            })
        
        if not query["bool"]["must"]:
            query = {"match_all": {}}
        
        body = {
            "query": query,
            "aggs": {
                "by_category": {
                    "terms": {
                        "field": "category_name",
                        "size": 100
                    },
                    "aggs": {
                        "total_amount": {
                            "sum": {"field": "amount"}
                        }
                    }
                }
            }
        }
        
        response = es.search(index=ElasticsearchService.INDEX_NAME, body=body)
        
        summary = {}
        for bucket in response["aggregations"]["by_category"]["buckets"]:
            summary[bucket["key"]] = {
                "count": bucket["doc_count"],
                "total": bucket["total_amount"]["value"]
            }
        
        return summary
    
    @staticmethod
    def add_transaction(transaction_data: Dict) -> bool:
        """
        Tilføjer en ny transaktion til Elasticsearch.
        """
        try:
            es.index(index=ElasticsearchService.INDEX_NAME, body=transaction_data)
            return True
        except Exception as e:
            print(f"Fejl ved tilføjelse af transaktion: {e}")
            return False
    
    @staticmethod
    def delete_transaction(transaction_id: int) -> bool:
        """
        Sletter en transaktion fra Elasticsearch.
        """
        try:
            es.delete(index=ElasticsearchService.INDEX_NAME, id=transaction_id)
            return True
        except Exception as e:
            print(f"Fejl ved sletning af transaktion: {e}")
            return False
