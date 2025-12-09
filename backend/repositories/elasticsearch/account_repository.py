# backend/repositories/elasticsearch/account_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import IAccountRepository

class ElasticsearchAccountRepository(IAccountRepository):
    """Elasticsearch implementation of account repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "accounts"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the accounts index exists."""
        if not self.es.indices.exists(index=self.index):
            self.es.indices.create(
                index=self.index,
                body={
                    "mappings": {
                        "properties": {
                            "idAccount": {"type": "integer"},
                            "name": {"type": "text"},
                            "saldo": {"type": "float"},
                            "User_idUser": {"type": "integer"}
                        }
                    }
                }
            )
    
    def get_all(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get all accounts from Elasticsearch, optionally filtered by user_id."""
        must_clauses = []
        
        if user_id is not None:
            must_clauses.append({"term": {"User_idUser": user_id}})
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        search_body = {
            "query": query,
            "sort": [{"idAccount": "asc"}]
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            accounts = []
            for hit in response["hits"]["hits"]:
                accounts.append(hit["_source"])
            return accounts
        except Exception as e:
            return []
    
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        """Get account by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=account_id)
            return response["_source"]
        except Exception:
            return None
    
    def create(self, account_data: Dict) -> Dict:
        """Create new account in Elasticsearch."""
        doc = {
            "idAccount": account_data.get("idAccount"),
            "name": account_data.get("name"),
            "saldo": account_data.get("saldo", 0.0),
            "User_idUser": account_data.get("User_idUser")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idAccount"],
                body=doc
            )
            self.es.indices.refresh(index=self.index)
            return doc
        except Exception as e:
            raise ValueError(f"Failed to create account: {str(e)}")
    
    def update(self, account_id: int, account_data: Dict) -> Dict:
        """Update account in Elasticsearch."""
        # Get existing account
        existing = self.get_by_id(account_id)
        if not existing:
            raise ValueError(f"Account {account_id} not found")
        
        # Merge updates
        updated = existing.copy()
        if "name" in account_data:
            updated["name"] = account_data["name"]
        if "saldo" in account_data:
            updated["saldo"] = account_data["saldo"]
        if "User_idUser" in account_data:
            updated["User_idUser"] = account_data["User_idUser"]
        
        try:
            self.es.index(
                index=self.index,
                id=account_id,
                body=updated
            )
            self.es.indices.refresh(index=self.index)
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update account: {str(e)}")
    
    def delete(self, account_id: int) -> bool:
        """Delete account from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=account_id)
            self.es.indices.refresh(index=self.index)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False

