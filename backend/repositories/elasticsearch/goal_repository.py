# backend/repositories/elasticsearch/goal_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import IGoalRepository

class ElasticsearchGoalRepository(IGoalRepository):
    """Elasticsearch implementation of goal repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "goals"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the goals index exists."""
        try:
            self.es.search(index=self.index, size=0)
        except Exception:
            try:
                self.es.indices.create(
                    index=self.index,
                    mappings={
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
                )
            except Exception as e:
                print(f"Note: Index {self.index} setup: {e}")
    
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"idGoal": "asc"}]
            )
            goals = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                # Ensure idGoal is set (use _id as fallback if idGoal is missing)
                if "idGoal" not in source or source.get("idGoal") is None:
                    try:
                        doc_id = hit.get("_id")
                        if doc_id is not None:
                            source["idGoal"] = int(doc_id)
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    source["idGoal"] = int(source["idGoal"])
                goals.append(source)
            return goals
        except Exception as e:
            return []
    
    def get_by_id(self, goal_id: int) -> Optional[Dict]:
        """Get goal by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=goal_id)
            source = response["_source"].copy()
            # Ensure idGoal is set (use _id as fallback if idGoal is missing)
            if "idGoal" not in source or source.get("idGoal") is None:
                try:
                    doc_id = response.get("_id")
                    if doc_id is not None:
                        source["idGoal"] = int(doc_id)
                    else:
                        source["idGoal"] = goal_id
                except (ValueError, TypeError):
                    source["idGoal"] = goal_id
            else:
                source["idGoal"] = int(source["idGoal"])
            return source
        except Exception:
            return None
    
    def create(self, goal_data: Dict) -> Dict:
        """Create new goal in Elasticsearch."""
        # Generate ID if not provided
        if "idGoal" not in goal_data or goal_data.get("idGoal") is None:
            try:
                # Get max ID from existing goals
                response = self.es.search(
                    index=self.index,
                    size=0,
                    aggs={"max_id": {"max": {"field": "idGoal"}}}
                )
                max_id = response.get("aggregations", {}).get("max_id", {}).get("value")
                goal_data["idGoal"] = int(max_id or 0) + 1
            except Exception:
                goal_data["idGoal"] = 1
        
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
                document=doc,
                refresh=True
            )
            # Ensure idGoal is set in returned data
            doc["idGoal"] = int(doc.get("idGoal"))
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
                document=updated,
                refresh=True
            )
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update goal: {str(e)}")
    
    def delete(self, goal_id: int) -> bool:
        """Delete goal from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=goal_id, refresh=True)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False

