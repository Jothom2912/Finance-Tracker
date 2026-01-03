# backend/repositories/elasticsearch/user_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import IUserRepository

class ElasticsearchUserRepository(IUserRepository):
    """Elasticsearch implementation of user repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "users"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the users index exists."""
        if not self.es.indices.exists(index=self.index):
            self.es.indices.create(
                index=self.index,
                body={
                    "mappings": {
                        "properties": {
                            "idUser": {"type": "integer"},
                            "username": {"type": "keyword"},
                            "email": {"type": "keyword"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
            )
    
    def get_all(self) -> List[Dict]:
        """Get all users from Elasticsearch."""
        search_body = {
            "query": {"match_all": {}},
            "sort": [{"idUser": "asc"}]
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            users = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                # IKKE inkluder password!
                users.append({
                    "idUser": source.get("idUser"),
                    "username": source.get("username"),
                    "email": source.get("email"),
                    "created_at": source.get("created_at")
                })
            return users
        except Exception as e:
            return []
    
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=user_id)
            source = response["_source"]
            # IKKE inkluder password!
            return {
                "idUser": source.get("idUser"),
                "username": source.get("username"),
                "email": source.get("email"),
                "created_at": source.get("created_at")
            }
        except Exception:
            return None
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username from Elasticsearch."""
        search_body = {
            "query": {
                "term": {"username": username}
            }
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            if response["hits"]["total"]["value"] > 0:
                source = response["hits"]["hits"][0]["_source"]
                # IKKE inkluder password!
                return {
                    "idUser": source.get("idUser"),
                    "username": source.get("username"),
                    "email": source.get("email"),
                    "created_at": source.get("created_at")
                }
            return None
        except Exception:
            return None
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email from Elasticsearch."""
        search_body = {
            "query": {
                "term": {"email": email}
            }
        }
        
        try:
            response = self.es.search(index=self.index, body=search_body)
            if response["hits"]["total"]["value"] > 0:
                source = response["hits"]["hits"][0]["_source"]
                # IKKE inkluder password!
                return {
                    "idUser": source.get("idUser"),
                    "username": source.get("username"),
                    "email": source.get("email"),
                    "created_at": source.get("created_at")
                }
            return None
        except Exception:
            return None
    
    def create(self, user_data: Dict) -> Dict:
        """Create new user in Elasticsearch."""
        doc = {
            "idUser": user_data.get("idUser"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "created_at": user_data.get("created_at")
            # IKKE gem password i Elasticsearch!
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idUser"],
                body=doc
            )
            self.es.indices.refresh(index=self.index)
            return {
                "idUser": doc["idUser"],
                "username": doc["username"],
                "email": doc["email"],
                "created_at": doc.get("created_at")
            }
        except Exception as e:
            raise ValueError(f"Failed to create user: {str(e)}")
    
    def authenticate_user(self, username_or_email: str) -> Optional[Dict]:
        """Get user data including password for authentication."""
        # Elasticsearch doesn't store passwords for security reasons
        return None

