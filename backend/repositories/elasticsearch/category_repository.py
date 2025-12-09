# backend/repositories/elasticsearch/category_repository.py
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch
from backend.database.elasticsearch import get_es_client
from backend.repositories.base import ICategoryRepository

class ElasticsearchCategoryRepository(ICategoryRepository):
    """Elasticsearch implementation of category repository."""
    
    def __init__(self, es_client: Elasticsearch = None):
        if es_client is None:
            self.es = get_es_client()
        else:
            self.es = es_client
        self.index = "categories"
    
    def get_all(self) -> List[Dict]:
        """Get all categories from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                body={"query": {"match_all": {}}, "size": 10000}
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
        try:
            response = self.es.index(
                index=self.index,
                body=category_data,
                id=category_data.get("idCategory"),
                refresh=True
            )
            category_data["idCategory"] = response["_id"]
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            return category_data
    
    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=category_id,
                body={"doc": category_data},
                refresh=True
            )
            return self.get_by_id(category_id) or category_data
        except Exception as e:
            print(f"Error updating category {category_id}: {e}")
            return category_data
    
    def delete(self, category_id: int) -> bool:
        """Delete category from Elasticsearch."""
        try:
            self.es.delete(index=self.index, id=category_id, refresh=True)
            return True
        except Exception as e:
            print(f"Error deleting category {category_id}: {e}")
            return False

