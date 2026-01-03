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
        try:
            self.es.search(index=self.index, size=0)
        except Exception:
            try:
                self.es.indices.create(
                    index=self.index,
                    mappings={
                        "properties": {
                            "idAccount": {"type": "integer"},
                            "name": {"type": "text"},
                            "saldo": {"type": "float"},
                            "User_idUser": {"type": "integer"}
                        }
                    }
                )
            except Exception as e:
                print(f"Note: Index {self.index} setup: {e}")
    
    def get_all(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get all accounts from Elasticsearch, optionally filtered by user_id."""
        must_clauses = []
        
        if user_id is not None:
            must_clauses.append({"term": {"User_idUser": user_id}})
        else:
            # If no user_id specified, still filter out accounts without User_idUser
            must_clauses.append({"exists": {"field": "User_idUser"}})
        
        query = {
            "bool": {
                "must": must_clauses if must_clauses else [{"match_all": {}}]
            }
        }
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"idAccount": "asc"}]
            )
            accounts = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                # Ensure idAccount is set (use _id as fallback if idAccount is missing)
                if "idAccount" not in source or source.get("idAccount") is None:
                    source["idAccount"] = int(hit["_id"]) if hit.get("_id") else None
                # Ensure User_idUser is set and matches filter (if user_id was specified)
                if user_id is not None:
                    # Only include accounts that belong to this user
                    if source.get("User_idUser") != user_id:
                        continue
                accounts.append(source)
            return accounts
        except Exception as e:
            return []
    
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        """Get account by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=account_id)
            source = response["_source"]
            # Ensure idAccount is set (use _id as fallback if idAccount is missing)
            if "idAccount" not in source or source.get("idAccount") is None:
                source["idAccount"] = int(response["_id"]) if response.get("_id") else account_id
            return source
        except Exception:
            return None
    
    def create(self, account_data: Dict) -> Dict:
        """Create new account in Elasticsearch."""
        # Generate ID if not provided
        if "idAccount" not in account_data or account_data.get("idAccount") is None:
            try:
                # Get max ID from existing accounts
                response = self.es.search(
                    index=self.index,
                    size=0,
                    aggs={"max_id": {"max": {"field": "idAccount"}}}
                )
                max_id = response.get("aggregations", {}).get("max_id", {}).get("value")
                account_data["idAccount"] = int(max_id or 0) + 1
            except Exception:
                account_data["idAccount"] = 1
        
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
                document=doc,
                refresh=True
            )
            return doc
        except Exception as e:
            raise ValueError(f"Failed to create account: {str(e)}")
    
    def update(self, account_id: int, account_data: Dict) -> Dict:
        """Update account in Elasticsearch."""
        existing = self.get_by_id(account_id)
        if not existing:
            raise ValueError(f"Account {account_id} not found")
        
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
                document=updated,
                refresh=True
            )
            return updated
        except Exception as e:
            raise ValueError(f"Failed to update account: {str(e)}")
    
    def delete(self, account_id: int) -> bool:
        """Delete account from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=account_id, refresh=True)
            return response["result"] in ["deleted", "not_found"]
        except Exception:
            return False
