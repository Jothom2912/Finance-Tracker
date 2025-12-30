# backend/repository/elasticsearch_repository.py
from typing import List, Dict, Optional
from datetime import date
from elasticsearch import Elasticsearch
from backend.repository.base_repository import ITransactionRepository, ICategoryRepository,IBudgetRepository,IUserRepository, IAccountRepository, IGoalRepository

class ElasticsearchTransactionRepository(ITransactionRepository):
    """Elasticsearch implementation of transaction repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = Elasticsearch(["http://localhost:9200"])
        else:
            self.es = es_client
        self.index = "transactions"
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
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
            must_clauses.append({"term": {"category_id": category_id}})
        
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
                refresh=True
            )
            transaction_data["id"] = response["_id"]
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
                    "fields": ["description", "name", "sender", "recipient"],
                    "fuzziness": "AUTO"
                }
            })
        
        if start_date:
            must_clauses.append({"range": {"date": {"gte": start_date.isoformat()}}})
        if end_date:
            must_clauses.append({"range": {"date": {"lte": end_date.isoformat()}}})
        if category_id is not None:
            must_clauses.append({"term": {"category_id": category_id}})
        
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
                        "count": {"value_count": {"field": "id"}}
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
        except Exception as e:
            print(f"Error getting category summary: {e}")
            return {}


class ElasticsearchCategoryRepository(ICategoryRepository):
    """Elasticsearch implementation of category repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = Elasticsearch(["http://localhost:9200"])
        else:
            self.es = es_client
        self.index = "categories"
    
    def get_all(self) -> List[Dict]:
        """Get all categories from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                body={"query": {"match_all": {}}, "size": 10000}
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error getting all categories: {e}")
            return []
    
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=category_id)
            return response["_source"]
        except Exception as e:
            print(f"Error getting category {category_id}: {e}")
            return None
    
    def create(self, name: str) -> Dict:
        """Create new category in Elasticsearch."""
        category_data = {"name": name, "type": "expense"}
        try:
            response = self.es.index(
                index=self.index,
                body=category_data,
                refresh=True
            )
            category_data["id"] = response["_id"]
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            return category_data
    
    def delete(self, category_id: int) -> bool:
        """Delete category from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=category_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting category {category_id}: {e}")
            return False
        
    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update transaction in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=category_id,
                body={"doc": category_data},
                refresh=True
            )
            return self.get_by_id(category_id) or category_data
        except Exception as e:
            print(f"Error updating transaction {category_id}: {e}")
            return category_data
        

class ElasticsearchBudgetRepository(IBudgetRepository):
    
    def get_all(self) -> List[Dict]:
        """Get all budgets from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                body={"query": {"match_all": {}}, "size": 10000}
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error getting all budgets: {e}")
            return []
        
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=category_id)
            return response["_source"]
        except Exception as e:
            print(f"Error getting category {category_id}: {e}")
            return None
        
    def create(self, name: str) -> Dict:
        """Create new category in Elasticsearch."""
        category_data = {"name": name, "type": "expense"}
        try:
            response = self.es.index(
                index=self.index,
                body=category_data,
                refresh=True
            )
            category_data["id"] = response["_id"]
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            return category_data
        
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=transaction_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting transaction {transaction_id}: {e}")
            return False
        
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
        
class ElasticsearchUserRepository(IUserRepository):
    def get_all(self) -> List[Dict]:
        """Get all users from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                body={"query": {"match_all": {}}, "size": 10000}
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []
        
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=category_id)
            return response["_source"]
        except Exception as e:
            print(f"Error getting category {category_id}: {e}")
            return None
        
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=transaction_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting transaction {transaction_id}: {e}")
            return False
        
    def create(self, name: str) -> Dict:
        """Create new category in Elasticsearch."""
        category_data = {"name": name, "type": "expense"}
        try:
            response = self.es.index(
                index=self.index,
                body=category_data,
                refresh=True
            )
            category_data["id"] = response["_id"]
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            return category_data

    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=category_id,
                body={"doc": category_data},
                refresh=True
            )
            return self.get_by_id(category_id) or category_data
        except Exception as e:
            print(f"Error updating category {category_id}: {e}")
            return category_data

class ElasticsearchAccountRepository(IAccountRepository):
    
    def get_all(self) -> List[Dict]:
        """Get all budgets from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                body={"query": {"match_all": {}}, "size": 10000}
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error getting all budgets: {e}")
            return []
        
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=category_id)
            return response["_source"]
        except Exception as e:
            print(f"Error getting category {category_id}: {e}")
            return None
    
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=transaction_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting transaction {transaction_id}: {e}")
            return False
        
    def create(self, name: str) -> Dict:
        """Create new category in Elasticsearch."""
        category_data = {"name": name, "type": "expense"}
        try:
            response = self.es.index(
                index=self.index,
                body=category_data,
                refresh=True
            )
            category_data["id"] = response["_id"]
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            return category_data

    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=category_id,
                body={"doc": category_data},
                refresh=True
            )
            return self.get_by_id(category_id) or category_data
        except Exception as e:
            print(f"Error updating category {category_id}: {e}")
            return category_data

class ElasticsearchGoalRepository(IGoalRepository):
    
    def get_all(self) -> List[Dict]:
        """Get all goals from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                body={"query": {"match_all": {}}, "size": 10000}
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            print(f"Error getting all goals: {e}")
            return []
        
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=category_id)
            return response["_source"]
        except Exception as e:
            print(f"Error getting category {category_id}: {e}")
            return None
        
    
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=transaction_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting transaction {transaction_id}: {e}")
            return False
        
    def create(self, name: str) -> Dict:
        """Create new category in Elasticsearch."""
        category_data = {"name": name, "type": "expense"}
        try:
            response = self.es.index(
                index=self.index,
                body=category_data,
                refresh=True
            )
            category_data["id"] = response["_id"]
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            return category_data

    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=category_id,
                body={"doc": category_data},
                refresh=True
            )
            return self.get_by_id(category_id) or category_data
        except Exception as e:
            print(f"Error updating category {category_id}: {e}")
            return category_data