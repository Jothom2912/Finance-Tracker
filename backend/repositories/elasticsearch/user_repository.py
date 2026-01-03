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
        try:
            # Check if index exists using search instead of indices.exists
            self.es.search(index=self.index, size=0)
        except Exception:
            # Index doesn't exist, create it
            try:
                self.es.indices.create(
                    index=self.index,
                    mappings={
                        "properties": {
                            "idUser": {"type": "integer"},
                            "username": {"type": "keyword"},
                            "email": {"type": "keyword"},
                            "password": {"type": "keyword"},  # TILFØJ password
                            "created_at": {"type": "date"}
                        }
                    }
                )
            except Exception as e:
                # Index might already exist
                print(f"Note: Index {self.index} setup: {e}")
    
    def get_all(self) -> List[Dict]:
        """Get all users from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                query={"match_all": {}},
                sort=[{"idUser": "asc"}]
            )
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
        try:
            response = self.es.search(
                index=self.index,
                query={"term": {"username": username}}
            )
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
        # Generate ID if not provided
        if "idUser" not in user_data or user_data.get("idUser") is None:
            try:
                # Get max ID from existing users
                response = self.es.search(
                    index=self.index,
                    size=0,
                    aggs={"max_id": {"max": {"field": "idUser"}}}
                )
                max_id = response.get("aggregations", {}).get("max_id", {}).get("value")
                user_data["idUser"] = int(max_id or 0) + 1
            except Exception:
                user_data["idUser"] = 1
        
        doc = {
            "idUser": user_data["idUser"],
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "password": user_data.get("password"),  # GEM password til auth!
            "created_at": user_data.get("created_at")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idUser"],
                document=doc
            )
            self.es.indices.refresh(index=self.index)
            
            # Return uden password
            return {
                "idUser": doc["idUser"],
                "username": doc["username"],
                "email": doc["email"],
                "created_at": doc.get("created_at")
            }
        except Exception as e:
            raise ValueError(f"Failed to create user: {str(e)}")
    
    def get_by_username_for_auth(self, username: str) -> Optional[Dict]:
        """Get user by username INCLUDING password - kun til authentication."""
        try:
            response = self.es.search(
                index=self.index,
                query={"term": {"username": username}}
            )
            if response["hits"]["total"]["value"] > 0:
                source = response["hits"]["hits"][0]["_source"]
                return {
                    "idUser": source.get("idUser"),
                    "username": source.get("username"),
                    "email": source.get("email"),
                    "password": source.get("password"),  # Inkluder password
                    "created_at": source.get("created_at")
                }
            return None
        except Exception:
            return None
    
    def get_by_email_for_auth(self, email: str) -> Optional[Dict]:
        """Get user by email INCLUDING password - kun til authentication."""
        try:
            response = self.es.search(
                index=self.index,
                query={"term": {"email": email}}
            )
            if response["hits"]["total"]["value"] > 0:
                source = response["hits"]["hits"][0]["_source"]
                return {
                    "idUser": source.get("idUser"),
                    "username": source.get("username"),
                    "email": source.get("email"),
                    "password": source.get("password"),
                    "created_at": source.get("created_at")
                }
            return None
        except Exception:
            return None

