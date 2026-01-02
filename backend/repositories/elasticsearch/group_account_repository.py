# backend/repositories/elasticsearch/goal_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import IGroupAccountRepository

class ElasticsearchGroupAccountRepository(IGroupAccountRepository):
    """Elasticsearch implementation of group account repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "group_accounts"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the group_accounts index exists."""
        if not self.es.indices.exists(index=self.index):
            self.es.indices.create(
                index=self.index,
                body={
                    "mappings": {
                        "properties": {
                            "idAccountGroups": {"type": "integer"},
                            "name": {"type": "text"}
                        }
                    }
                }
            )
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all group accounts from Elasticsearch."""
        # No filter for account_id since AccountGroups doesn't have it
        query = {"match_all": {}}
        
        search_body = {
            "query": query,
            "sort": [{"idAccountGroups": "asc"}]
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            group_accounts = []
            for hit in response["hits"]["hits"]:
                group_accounts.append(hit["_source"])
            return group_accounts
        except Exception as e:
            return []
    
    def get_by_id(self, group_account_id: int) -> Optional[Dict]:
        """Get group account by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=group_account_id)
            return response["_source"]
        except Exception:
            return None
    
    def create(self, group_account_data: Dict) -> Dict:
        """Create new group account in Elasticsearch."""
        doc = {
            "idAccountGroups": group_account_data.get("idAccountGroups"),
            "name": group_account_data.get("name")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idAccountGroups"],
                body=doc
            )
            self.es.indices.refresh(index=self.index)
            return doc
        except Exception as e:
            raise ValueError(f"Failed to create group account: {str(e)}")
    
    def update(self, group_account_id: int, group_account_data: Dict) -> Dict:
        """Update group account in Elasticsearch."""
        # Get existing group account
        existing = self.get_by_id(group_account_id)
        if not existing:
            raise ValueError(f"Group account {group_account_id} not found")
        
        # Merge updates
        updated = existing.copy()
        if "name" in group_account_data:
            updated["name"] = group_account_data["name"]
        
        try:
            self.es.index(
                index=self.index,
                id=group_account_id,
                body=updated
            )
            self.es.indices.refresh(index=self.index)
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update group account: {str(e)}")
    
    def delete(self, group_account_id: int) -> bool:
        """Delete group account from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=group_account_id)
            self.es.indices.refresh(index=self.index)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False
