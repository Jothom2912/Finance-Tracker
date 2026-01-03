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
        try:
            self.es.search(index=self.index, size=0)
        except Exception:
            try:
                self.es.indices.create(
                    index=self.index,
                    mappings={
                        "properties": {
                            "idBudget": {"type": "integer"},
                            "amount": {"type": "float"},
                            "budget_date": {"type": "date"},
                            "Account_idAccount": {"type": "integer"}
                        }
                    }
                )
            except Exception as e:
                print(f"Note: Index {self.index} setup: {e}")
    
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"idBudget": "asc"}]
            )
            budgets = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                # Ensure idBudget is set (use _id as fallback if idBudget is missing)
                if "idBudget" not in source or source.get("idBudget") is None:
                    try:
                        doc_id = hit.get("_id")
                        if doc_id is not None:
                            source["idBudget"] = int(doc_id)
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    source["idBudget"] = int(source["idBudget"])
                budgets.append(source)
            return budgets
        except Exception as e:
            return []
    
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        """Get budget by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=budget_id)
            source = response["_source"].copy()
            # Ensure idBudget is set (use _id as fallback if idBudget is missing)
            if "idBudget" not in source or source.get("idBudget") is None:
                try:
                    doc_id = response.get("_id")
                    if doc_id is not None:
                        source["idBudget"] = int(doc_id)
                    else:
                        source["idBudget"] = budget_id
                except (ValueError, TypeError):
                    source["idBudget"] = budget_id
            else:
                source["idBudget"] = int(source["idBudget"])
            return source
        except Exception:
            return None
    
    def create(self, budget_data: Dict) -> Dict:
        """Create new budget in Elasticsearch."""
        # Generate ID if not provided
        if "idBudget" not in budget_data or budget_data.get("idBudget") is None:
            try:
                # Get max ID from existing budgets
                response = self.es.search(
                    index=self.index,
                    size=0,
                    aggs={"max_id": {"max": {"field": "idBudget"}}}
                )
                max_id = response.get("aggregations", {}).get("max_id", {}).get("value")
                budget_data["idBudget"] = int(max_id or 0) + 1
            except Exception:
                budget_data["idBudget"] = 1
        
        doc = {
            "idBudget": budget_data.get("idBudget"),
            "amount": budget_data.get("amount"),
            "budget_date": budget_data.get("budget_date"),
            "Account_idAccount": budget_data.get("Account_idAccount")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idBudget"],
                document=doc,
                refresh=True
            )
            # Ensure idBudget is set in returned data
            doc["idBudget"] = int(doc.get("idBudget"))
            return doc
        except Exception as e:
            raise ValueError(f"Failed to create budget: {str(e)}")
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        """Update budget in Elasticsearch."""
        existing = self.get_by_id(budget_id)
        if not existing:
            raise ValueError(f"Budget {budget_id} not found")
        
        updated = existing.copy()
        if "amount" in budget_data:
            updated["amount"] = budget_data["amount"]
        if "budget_date" in budget_data:
            updated["budget_date"] = budget_data["budget_date"]
        if "Account_idAccount" in budget_data:
            updated["Account_idAccount"] = budget_data["Account_idAccount"]
        
        try:
            self.es.index(
                index=self.index,
                id=budget_id,
                document=updated,
                refresh=True
            )
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update budget: {str(e)}")
    
    def delete(self, budget_id: int) -> bool:
        """Delete budget from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=budget_id, refresh=True)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False
