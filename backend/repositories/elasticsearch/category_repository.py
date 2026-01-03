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
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure the categories index exists."""
        try:
            self.es.search(index=self.index, size=0)
        except Exception as e:
            # Handle API version mismatch (client 9.x vs server 7/8)
            if "version" in str(e).lower() or "compatible-with" in str(e).lower():
                # If version error, try to work around it by catching and continuing
                # The actual operations will fail later, but at least we tried
                pass
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
            except Exception as create_error:
                # If it's a version error, we can't fix it here - need to downgrade client or upgrade server
                if "version" not in str(create_error).lower() and "compatible-with" not in str(create_error).lower():
                    print(f"Note: Index {self.index} setup: {create_error}")
    
    def get_all(self) -> List[Dict]:
        """Get all categories from Elasticsearch."""
        try:
            response = self.es.search(
                index=self.index,
                query={"match_all": {}},
                size=10000
            )
            categories = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                # Ensure idCategory is set (use _id as fallback if idCategory is missing)
                if "idCategory" not in source or source.get("idCategory") is None:
                    try:
                        doc_id = hit.get("_id")
                        if doc_id is not None:
                            source["idCategory"] = int(doc_id)
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    source["idCategory"] = int(source["idCategory"])
                categories.append(source)
            return categories
        except Exception as e:
            print(f"Error getting all categories: {e}")
            return []
    
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index, id=category_id)
            source = response["_source"].copy()
            # Ensure idCategory is set (use _id as fallback if idCategory is missing)
            if "idCategory" not in source or source.get("idCategory") is None:
                try:
                    doc_id = response.get("_id")
                    if doc_id is not None:
                        source["idCategory"] = int(doc_id)
                    else:
                        source["idCategory"] = category_id
                except (ValueError, TypeError):
                    source["idCategory"] = category_id
            else:
                source["idCategory"] = int(source["idCategory"])
            return source
        except Exception as e:
            print(f"Error getting category {category_id}: {e}")
            return None
    
    def create(self, category_data: Dict) -> Dict:
        """Create new category in Elasticsearch."""
        # Generate ID if not provided
        if "idCategory" not in category_data or category_data.get("idCategory") is None:
            try:
                # Get max ID from existing categories
                response = self.es.search(
                    index=self.index,
                    size=0,
                    aggs={"max_id": {"max": {"field": "idCategory"}}}
                )
                max_id = response.get("aggregations", {}).get("max_id", {}).get("value")
                category_data["idCategory"] = int(max_id or 0) + 1
            except Exception:
                category_data["idCategory"] = 1
        
        try:
            self.es.index(
                index=self.index,
                document=category_data,
                id=category_data.get("idCategory"),
                refresh=True
            )
            # Ensure idCategory is set in returned data
            category_data["idCategory"] = int(category_data.get("idCategory"))
            return category_data
        except Exception as e:
            print(f"Error creating category: {e}")
            raise ValueError(f"Failed to create category: {str(e)}")
    
    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Elasticsearch."""
        try:
            self.es.update(
                index=self.index,
                id=category_id,
                doc=category_data,
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
