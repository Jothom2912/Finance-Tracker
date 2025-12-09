# backend/repositories/neo4j/category_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import ICategoryRepository

class Neo4jCategoryRepository(ICategoryRepository):
    """Neo4j implementation of category repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(self) -> List[Dict]:
        """Get all categories from Neo4j."""
        query = "MATCH (c:Category) RETURN c ORDER BY c.idCategory"
        with self._get_session() as session:
            result = session.run(query)
            return [{"idCategory": record["c"]["idCategory"], 
                    "name": record["c"]["name"],
                    "type": record["c"]["type"]} 
                   for record in result]
    
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID from Neo4j."""
        query = "MATCH (c:Category {idCategory: $id}) RETURN c"
        with self._get_session() as session:
            result = session.run(query, id=category_id)
            record = result.single()
            if record:
                c = record["c"]
                return {
                    "idCategory": c["idCategory"],
                    "name": c["name"],
                    "type": c["type"]
                }
            return None
    
    def create(self, category_data: Dict) -> Dict:
        """Create new category in Neo4j."""
        query = """
        CREATE (c:Category {
            idCategory: $idCategory,
            name: $name,
            type: $type
        })
        RETURN c
        """
        with self._get_session() as session:
            result = session.run(query, **category_data)
            record = result.single()
            if record:
                c = record["c"]
                return {
                    "idCategory": c["idCategory"],
                    "name": c["name"],
                    "type": c["type"]
                }
            return category_data
    
    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category in Neo4j."""
        query = """
        MATCH (c:Category {idCategory: $id})
        SET c.name = $name, c.type = $type
        RETURN c
        """
        with self._get_session() as session:
            result = session.run(query, id=category_id, **category_data)
            record = result.single()
            if record:
                c = record["c"]
                return {
                    "idCategory": c["idCategory"],
                    "name": c["name"],
                    "type": c["type"]
                }
            return category_data
    
    def delete(self, category_id: int) -> bool:
        """Delete category from Neo4j."""
        query = """
        MATCH (c:Category {idCategory: $id})
        DETACH DELETE c
        """
        with self._get_session() as session:
            result = session.run(query, id=category_id)
            return result.consume().counters.nodes_deleted > 0

