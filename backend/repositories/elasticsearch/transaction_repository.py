# backend/repositories/elasticsearch/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from elasticsearch import Elasticsearch
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
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"date": "desc"}],
                from_=offset,
                size=limit
            )
            transactions = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                # Ensure idTransaction is set (use _id as fallback if idTransaction is missing)
                if "idTransaction" not in source or source.get("idTransaction") is None:
                    try:
                        doc_id = hit.get("_id")
                        if doc_id is not None:
                            source["idTransaction"] = int(doc_id)
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    source["idTransaction"] = int(source["idTransaction"])
                transactions.append(source)
            return transactions
        except Exception as e:
            print(f"Error searching Elasticsearch: {e}")
            return []
    
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        """Get single transaction by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=transaction_id)
            source = response["_source"].copy()
            # Ensure idTransaction is set (use _id as fallback if idTransaction is missing)
            if "idTransaction" not in source or source.get("idTransaction") is None:
                try:
                    doc_id = response.get("_id")
                    if doc_id is not None:
                        source["idTransaction"] = int(doc_id)
                    else:
                        source["idTransaction"] = transaction_id
                except (ValueError, TypeError):
                    source["idTransaction"] = transaction_id
            else:
                source["idTransaction"] = int(source["idTransaction"])
            return source
        except Exception as e:
            print(f"Error getting transaction {transaction_id}: {e}")
            return None
    
    def create(self, transaction_data: Dict) -> Dict:
        """Create new transaction in Elasticsearch."""
        # Generate ID if not provided
        if "idTransaction" not in transaction_data or transaction_data.get("idTransaction") is None:
            try:
                # Get max ID from existing transactions
                response = self.es.search(
                    index=self.index,
                    size=0,
                    aggs={"max_id": {"max": {"field": "idTransaction"}}}
                )
                max_id = response.get("aggregations", {}).get("max_id", {}).get("value")
                transaction_data["idTransaction"] = int(max_id or 0) + 1
            except Exception:
                transaction_data["idTransaction"] = 1
        
        try:
            response = self.es.index(
                index=self.index,
                document=transaction_data,
                id=transaction_data.get("idTransaction"),
                refresh=True
            )
            # Ensure idTransaction is set in returned data
            transaction_data["idTransaction"] = int(transaction_data.get("idTransaction"))
            return transaction_data
        except Exception as e:
            print(f"Error creating transaction: {e}")
            raise ValueError(f"Failed to create transaction: {str(e)}")
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        """Update transaction in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=transaction_id,
                doc=transaction_data,
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"date": "desc"}],
                size=1000
            )
            transactions = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                # Ensure idTransaction is set (use _id as fallback if idTransaction is missing)
                if "idTransaction" not in source or source.get("idTransaction") is None:
                    try:
                        doc_id = hit.get("_id")
                        if doc_id is not None:
                            source["idTransaction"] = int(doc_id)
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    source["idTransaction"] = int(source["idTransaction"])
                transactions.append(source)
            return transactions
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                aggs={
                    "by_category": {
                        "terms": {"field": "category_name", "size": 100},
                        "aggs": {
                            "total_amount": {"sum": {"field": "amount"}},
                            "count": {"value_count": {"field": "idTransaction"}}
                        }
                    }
                },
                size=0
            )
            summary = {}
            
            for bucket in response["aggregations"]["by_category"]["buckets"]:
                category_name = bucket["key"]
                summary[category_name] = {
                    "count": int(bucket["count"]["value"]),
                    "total": bucket["total_amount"]["value"]
                }
            
            return summary
        except Exception as e:
            print(f"Error getting category summary: {e}")
            return {}
