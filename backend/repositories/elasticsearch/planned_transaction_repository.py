# backend/repositories/elasticsearch/goal_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import IPlannedTransaction

class ElasticsearchPlannedTransactionRepository(IPlannedTransaction):
    """Elasticsearch implementation of planned transaction repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "planned_transactions"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the planned transactions index exists."""
        if not self.es.indices.exists(index=self.index):
            self.es.indices.create(
                index=self.index,
                body={
                    "mappings": {
                        "properties": {
                            "idGoal": {"type": "integer"},
                            "name": {"type": "text"},
                            "target_amount": {"type": "float"},
                            "current_amount": {"type": "float"},
                            "target_date": {"type": "date"},
                            "status": {"type": "keyword"},
                            "Account_idAccount": {"type": "integer"}
                        }
                    }
                }
            )
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all goals from Elasticsearch, optionally filtered by account_id."""
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
            "sort": [{"idGoal": "asc"}]
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            goals = []
            for hit in response["hits"]["hits"]:
                goals.append(hit["_source"])
            return goals
        except Exception as e:
            return []
    
    def get_by_id(self, goal_id: int) -> Optional[Dict]:
        """Get goal by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=goal_id)
            return response["_source"]
        except Exception:
            return None
    
    def create(self, goal_data: Dict) -> Dict:
        """Create new goal in Elasticsearch."""
        doc = {
            "idGoal": goal_data.get("idGoal"),
            "name": goal_data.get("name"),
            "target_amount": goal_data.get("target_amount"),
            "current_amount": goal_data.get("current_amount", 0.0),
            "target_date": goal_data.get("target_date"),
            "status": goal_data.get("status", "active"),
            "Account_idAccount": goal_data.get("Account_idAccount")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idGoal"],
                body=doc
            )
            self.es.indices.refresh(index=self.index)
            return doc
        except Exception as e:
            raise ValueError(f"Failed to create goal: {str(e)}")
    
    def update(self, goal_id: int, goal_data: Dict) -> Dict:
        """Update goal in Elasticsearch."""
        # Get existing goal
        existing = self.get_by_id(goal_id)
        if not existing:
            raise ValueError(f"Goal {goal_id} not found")
        
        # Merge updates
        updated = existing.copy()
        if "name" in goal_data:
            updated["name"] = goal_data["name"]
        if "target_amount" in goal_data:
            updated["target_amount"] = goal_data["target_amount"]
        if "current_amount" in goal_data:
            updated["current_amount"] = goal_data["current_amount"]
        if "target_date" in goal_data:
            updated["target_date"] = goal_data["target_date"]
        if "status" in goal_data:
            updated["status"] = goal_data["status"]
        if "Account_idAccount" in goal_data:
            updated["Account_idAccount"] = goal_data["Account_idAccount"]
        
        try:
            self.es.index(
                index=self.index,
                id=goal_id,
                body=updated
            )
            self.es.indices.refresh(index=self.index)
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update goal: {str(e)}")
    
    def delete(self, goal_id: int) -> bool:
        """Delete goal from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=goal_id)
            self.es.indices.refresh(index=self.index)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False
