# backend/repositories/elasticsearch/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from elasticsearch import Elasticsearch
from backend.config import ELASTICSEARCH_HOST
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import ITransactionRepository

class ElasticsearchTransactionRepository(ITransactionRepository):
    """Elasticsearch implementation of transaction repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "transactions"
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        type: Optional[str] = None,
        month: Optional[str] = None,
        year: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get transactions from Elasticsearch with optional filters."""
        must_clauses = []
        
        if start_date:
            must_clauses.append({"range": {"date": {"gte": start_date.isoformat()}}})
        if end_date:
            must_clauses.append({"range": {"date": {"lte": end_date.isoformat()}}})
        if category_id is not None:
            must_clauses.append({"term": {"Category_idCategory": category_id}})
        if account_id is not None:
            must_clauses.append({"term": {"Account_idAccount": account_id}})
        if type:
            must_clauses.append({"term": {"type": type}})
        if month:
            must_clauses.append({"term": {"month": month}})
        if year:
            must_clauses.append({"term": {"year": year}})
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        search_body = {
            "query": query,
            "sort": [{"date": "desc"}],
            "from": offset,
            "size": limit
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error searching Elasticsearch: {e}")
            return []
    
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        """Get single transaction by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=transaction_id)
            return response["_source"]
        except Exception as e:
            print(f"Error getting transaction {transaction_id}: {e}")
            return None
    
    def create(self, transaction_data: Dict) -> Dict:
        """Create new transaction in Elasticsearch."""
        try:
            response = self.es.index(
                index=self.index,
                body=transaction_data,
                id=transaction_data.get("idTransaction"),
                refresh=True
            )
            transaction_data["idTransaction"] = response["_id"]
            return transaction_data
        except Exception as e:
            print(f"Error creating transaction: {e}")
            return transaction_data
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        """Update transaction in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=transaction_id,
                body={"doc": transaction_data},
                refresh=True
            )
            return self.get_by_id(transaction_id) or transaction_data
        except Exception as e:
            print(f"Error updating transaction {transaction_id}: {e}")
            return transaction_data
    
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=transaction_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting transaction {transaction_id}: {e}")
            return False
    
    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None
    ) -> List[Dict]:
        """Search transactions in Elasticsearch."""
        must_clauses = []
        
        if search_text:
            must_clauses.append({
                "multi_match": {
                    "query": search_text,
                    "fields": ["description", "category_name", "account_name"],
                    "fuzziness": "AUTO"
                }
            })
        
        if start_date:
            must_clauses.append({"range": {"date": {"gte": start_date.isoformat()}}})
        if end_date:
            must_clauses.append({"range": {"date": {"lte": end_date.isoformat()}}})
        if category_id is not None:
            must_clauses.append({"term": {"Category_idCategory": category_id}})
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        search_body = {
            "query": query,
            "sort": [{"date": "desc"}],
            "size": 1000
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error searching Elasticsearch: {e}")
            return []
    
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """Get summary aggregated by category from Elasticsearch."""
        must_clauses = []
        
        if start_date:
            must_clauses.append({"range": {"date": {"gte": start_date.isoformat()}}})
        if end_date:
            must_clauses.append({"range": {"date": {"lte": end_date.isoformat()}}})
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        search_body = {
            "query": query,
            "aggs": {
                "by_category": {
                    "terms": {"field": "category_name", "size": 100},
                    "aggs": {
                        "total_amount": {"sum": {"field": "amount"}},
                        "count": {"value_count": {"field": "idTransaction"}}
                    }
                }
            },
            "size": 0
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            summary = {}
            
            for bucket in response["aggregations"]["by_category"]["buckets"]:
                category_name = bucket["key"]
                summary[category_name] = {
                    "count": int(bucket["count"]["value"]),
                    "total": bucket["total_amount"]["value"]
                }
            
            return summary
    
    def get_expenses_by_category_for_period(
        self,
        month: int,
        year: int,
        account_id: int
    ) -> Dict[int, float]:
        """Get aggregated expenses by category for a specific month/year and account from Elasticsearch."""
        must_clauses = [
            {"term": {"Account_idAccount": account_id}},
            {"range": {"amount": {"lt": 0}}},  # Expenses are negative
            {"range": {"date": {
                "gte": f"{year:04d}-{month:02d}-01",
                "lt": f"{year:04d}-{month+1:02d}-01" if month < 12 else f"{year+1:04d}-01-01"
            }}}
        ]
        
        search_body = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "aggs": {
                "by_category": {
                    "terms": {"field": "Category_idCategory", "size": 100},
                    "aggs": {
                        "total_spent": {"sum": {"field": "amount"}}
                    }
                }
            },
            "size": 0
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            expenses = {}
            
            for bucket in response["aggregations"]["by_category"]["buckets"]:
                category_id = bucket["key"]
                total_spent = abs(bucket["total_spent"]["value"])  # Make positive
                expenses[category_id] = total_spent
            
            return expenses
        except Exception as e:
            print(f"Error getting expenses by category: {e}")
            return {}
        except Exception as e:
            print(f"Error getting category summary: {e}")
            return {}

