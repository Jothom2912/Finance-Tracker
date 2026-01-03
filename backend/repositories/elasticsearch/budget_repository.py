# backend/repositories/elasticsearch/budget_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import IBudgetRepository

class ElasticsearchBudgetRepository(IBudgetRepository):
    """Elasticsearch implementation of budget repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "budgets"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the budgets index exists."""
        if not self.es.indices.exists(index=self.index):
            self.es.indices.create(
                index=self.index,
                body={
                    "mappings": {
                        "properties": {
                            "idBudget": {"type": "integer"},
                            "amount": {"type": "float"},
                            "budget_date": {"type": "date"},
                            "Account_idAccount": {"type": "integer"},
                            "categories": {
                                "type": "nested",
                                "properties": {
                                    "idCategory": {"type": "integer"},
                                    "name": {"type": "text"}
                                }
                            }
                        }
                    }
                }
            )
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all budgets from Elasticsearch, optionally filtered by account_id."""
        must_clauses = []
        
        if account_id is not None:
            must_clauses.append({"term": {"Account_idAccount": account_id}})
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        search_body = {
            "query": query,
            "sort": [{"idBudget": "asc"}]
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            budgets = []
            for hit in response["hits"]["hits"]:
                budgets.append(hit["_source"])
            return budgets
        except Exception as e:
            return []
    
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        """Get budget by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=budget_id)
            return response["_source"]
        except Exception:
            return None
    
    def create(self, budget_data: Dict) -> Dict:
        """Create new budget in Elasticsearch."""
        doc = {
            "idBudget": budget_data.get("idBudget"),
            "amount": budget_data.get("amount"),
            "budget_date": budget_data.get("budget_date"),
            "Account_idAccount": budget_data.get("Account_idAccount"),
            "categories": budget_data.get("categories", [])
        }
        
        # Handle category association if category_id is provided
        category_id = budget_data.get("category_id")
        if category_id:
            # For simplicity, add the category_id to categories list
            # In a real implementation, you might want to fetch category details
            doc["categories"].append({"idCategory": category_id})
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idBudget"],
                body=doc
            )
            self.es.indices.refresh(index=self.index)
            return doc
        except Exception as e:
            raise ValueError(f"Failed to create budget: {str(e)}")
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        """Update budget in Elasticsearch."""
        # Get existing budget
        existing = self.get_by_id(budget_id)
        if not existing:
            raise ValueError(f"Budget {budget_id} not found")
        
        # Merge updates
        updated = existing.copy()
        if "amount" in budget_data:
            updated["amount"] = budget_data["amount"]
        if "budget_date" in budget_data:
            updated["budget_date"] = budget_data["budget_date"]
        if "Account_idAccount" in budget_data:
            updated["Account_idAccount"] = budget_data["Account_idAccount"]
        
        # Handle category association update if category_id is provided
        category_id = budget_data.get("category_id")
        if category_id is not None:
            # Replace categories with new one
            updated["categories"] = [{"idCategory": category_id}]
        
        try:
            self.es.index(
                index=self.index,
                id=budget_id,
                body=updated
            )
            self.es.indices.refresh(index=self.index)
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update budget: {str(e)}")
    
    def delete(self, budget_id: int) -> bool:
        """Delete budget from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=budget_id)
            self.es.indices.refresh(index=self.index)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False

