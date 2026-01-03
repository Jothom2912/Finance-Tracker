# backend/repository/elasticsearch_repository.py
from typing import List, Dict, Optional
from datetime import date
from elasticsearch import Elasticsearch
from backend.database import get_es_client
from backend.repository.base_repository import (
    ITransactionRepository,
    ICategoryRepository,
    IUserRepository,
    IAccountRepository,
    IBudgetRepository
)

class ElasticsearchTransactionRepository(ITransactionRepository):
    """Elasticsearch implementation of transaction repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"date": "desc"}],
                from_=offset,
                size=limit
            )
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
                document=transaction_data,
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
                doc=transaction_data,
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"date": "desc"}],
                size=1000
            )
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                aggs={
                    "by_category": {
                        "terms": {"field": "category_name", "size": 100},
                        "aggs": {
                            "total_amount": {"sum": {"field": "amount"}},
                            "count": {"value_count": {"field": "id"}}
                        }
                    }
                },
                size=0
            )
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
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "categories"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the categories index exists."""
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
                            "idCategory": {"type": "integer"},
                            "name": {"type": "keyword"},
                            "type": {"type": "keyword"}
                        }
                    }
                )
            except Exception as e:
                # Index might already exist
                print(f"Note: Index {self.index} setup: {e}")
    
    def get_all(self) -> List[Dict]:
        """Get all categories from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                query={"match_all": {}},
                size=10000
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
    
    def create(self, category_data: Dict) -> Dict:
        """Create new category in Elasticsearch."""
        doc = {
            "idCategory": category_data.get("idCategory"),
            "name": category_data.get("name"),
            "type": category_data.get("type", "expense")
        }
        try:
            self.es.index(
                index=self.index,
                id=doc.get("idCategory"),
                document=doc,
                refresh=True
            )
            return doc
        except Exception as e:
            print(f"Error creating category: {e}")
            return doc
    
    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Elasticsearch."""
        existing = self.get_by_id(category_id)
        if not existing:
            raise ValueError(f"Category {category_id} not found")
        
        updated = existing.copy()
        if "name" in category_data:
            updated["name"] = category_data["name"]
        if "type" in category_data:
            updated["type"] = category_data["type"]
        
        try:
            self.es.index(
                index=self.index,
                id=category_id,
                document=updated,
                refresh=True
            )
            return updated
        except Exception as e:
            print(f"Error updating category {category_id}: {e}")
            return updated
    
    def delete(self, category_id: int) -> bool:
        """Delete category from Elasticsearch."""
        try:
            response = self.es.delete(index=self.index, id=category_id, refresh=True)
            return response["result"] in ["deleted", "not_found"]
        except Exception as e:
            print(f"Error deleting category {category_id}: {e}")
            return False


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
                            "password": {"type": "keyword"},
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
            print(f"Error getting all users: {e}")
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
        doc = {
            "idUser": user_data.get("idUser"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "password": user_data.get("password"),
            "created_at": user_data.get("created_at")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idUser"],
                document=doc,
                refresh=True
            )
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
                    "password": source.get("password"),  # Inkluder password til auth
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
            # Check if index exists using search instead of indices.exists
            self.es.search(index=self.index, size=0)
        except Exception:
            # Index doesn't exist, create it
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
                # Index might already exist
                print(f"Note: Index {self.index} setup: {e}")
    
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
        
        try:
            response = self.es.search(
                index=self.index,
                query=query,
                sort=[{"idAccount": "asc"}]
            )
            accounts = []
            for hit in response["hits"]["hits"]:
                accounts.append(hit["_source"])
            return accounts
        except Exception as e:
            print(f"Error getting all accounts: {e}")
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
            # Check if index exists using search instead of indices.exists
            self.es.search(index=self.index, size=0)
        except Exception:
            # Index doesn't exist, create it
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
                # Index might already exist
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
                budgets.append(hit["_source"])
            return budgets
        except Exception as e:
            print(f"Error getting all budgets: {e}")
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
            "Account_idAccount": budget_data.get("Account_idAccount")
        }
        
        try:
            self.es.index(
                index=self.index,
                id=doc["idBudget"],
                document=doc,
                refresh=True
            )
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
