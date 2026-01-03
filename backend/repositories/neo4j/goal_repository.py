# backend/repositories/neo4j/goal_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IGoalRepository


def _convert_neo4j_date(value):
    """Konverter Neo4j date til Python date/string."""
    if value is None:
        return None
    if hasattr(value, 'to_native'):
        return value.to_native()  # Konverterer neo4j.time.Date til datetime.date
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)

class Neo4jGoalRepository(IGoalRepository):
    """Neo4j implementation of goal repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all goals from Neo4j, optionally filtered by account_id."""
        if account_id:
            query = """
            MATCH (a:Account {idAccount: $account_id})-[:HAS_GOAL]->(g:Goal)
            RETURN g, a
            ORDER BY g.idGoal
            """
            params = {"account_id": account_id}
        else:
            query = "MATCH (g:Goal) RETURN g ORDER BY g.idGoal"
            params = {}
        
        with self._get_session() as session:
            result = session.run(query, **params)
            goals = []
            for record in result:
                g = record["g"]
                goals.append({
                    "idGoal": g["idGoal"],
                    "name": g.get("name"),
                    "target_amount": float(g.get("target_amount", 0.0)),
                    "current_amount": float(g.get("current_amount", 0.0)),
                    "target_date": _convert_neo4j_date(g.get("target_date")),
                    "status": g.get("status"),
                    "Account_idAccount": record.get("a", {}).get("idAccount") if "a" in record else None
                })
            return goals
    
    def get_by_id(self, goal_id: int) -> Optional[Dict]:
        """Get goal by ID from Neo4j."""
        query = """
        MATCH (a:Account)-[:HAS_GOAL]->(g:Goal {idGoal: $id})
        RETURN g, a
        """
        with self._get_session() as session:
            result = session.run(query, id=goal_id)
            record = result.single()
            if record:
                g = record["g"]
                return {
                    "idGoal": g["idGoal"],
                    "name": g.get("name"),
                    "target_amount": float(g.get("target_amount", 0.0)),
                    "current_amount": float(g.get("current_amount", 0.0)),
                    "target_date": _convert_neo4j_date(g.get("target_date")),
                    "status": g.get("status"),
                    "Account_idAccount": record["a"]["idAccount"] if "a" in record else None
                }
            return None
    
    def create(self, goal_data: Dict) -> Dict:
        """Create new goal in Neo4j."""
        # Generate ID if not provided
        if "idGoal" not in goal_data:
            query_max = "MATCH (g:Goal) RETURN MAX(g.idGoal) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                goal_data["idGoal"] = max_id + 1
        
        query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        CREATE (g:Goal {
            idGoal: $idGoal,
            name: $name,
            target_amount: $target_amount,
            current_amount: $current_amount,
            target_date: $target_date,
            status: $status
        })
        CREATE (a)-[:HAS_GOAL]->(g)
        RETURN g, a
        """
        with self._get_session() as session:
            result = session.run(
                query,
                idGoal=goal_data.get("idGoal"),
                name=goal_data.get("name"),
                target_amount=goal_data.get("target_amount"),
                current_amount=goal_data.get("current_amount", 0.0),
                target_date=goal_data.get("target_date"),
                status=goal_data.get("status", "active"),
                Account_idAccount=goal_data.get("Account_idAccount")
            )
            record = result.single()
            if record:
                return self.get_by_id(goal_data["idGoal"])
            return goal_data
    
    def update(self, goal_id: int, goal_data: Dict) -> Dict:
        """Update goal in Neo4j."""
        query = """
        MATCH (g:Goal {idGoal: $id})
        SET g.name = $name,
            g.target_amount = $target_amount,
            g.current_amount = $current_amount,
            g.target_date = $target_date,
            g.status = $status
        RETURN g
        """
        with self._get_session() as session:
            result = session.run(
                query,
                id=goal_id,
                name=goal_data.get("name"),
                target_amount=goal_data.get("target_amount"),
                current_amount=goal_data.get("current_amount", 0.0),
                target_date=goal_data.get("target_date"),
                status=goal_data.get("status", "active")
            )
            record = result.single()
            if record:
                return self.get_by_id(goal_id)
            raise ValueError(f"Goal {goal_id} not found")
    
    def delete(self, goal_id: int) -> bool:
        """Delete goal from Neo4j."""
        query = """
        MATCH (g:Goal {idGoal: $id})
        DETACH DELETE g
        """
        with self._get_session() as session:
            result = session.run(query, id=goal_id)
            return result.consume().counters.nodes_deleted > 0

