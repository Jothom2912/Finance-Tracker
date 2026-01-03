# backend/repositories/neo4j/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IGroupAccountRepository

class Neo4jGroupAccountRepository(IGroupAccountRepository):
    """Neo4j implementation of group account repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all group accounts from Neo4j."""
        query = """
        MATCH (ag:AccountGroups)
        OPTIONAL MATCH (ag)-[:HAS_MEMBER]->(u:User)
        RETURN ag, collect(u) as users
        ORDER BY ag.idAccountGroups
        """
        with self._get_session() as session:
            result = session.run(query)
            group_accounts = []
            for record in result:
                ag = record["ag"]
                users = record["users"]
                group_accounts.append({
                    "idAccountGroups": ag["idAccountGroups"],
                    "name": ag["name"],
                    "max_users": ag.get("max_users", 20),  # Default to 20 if not set
                    "users": [{"idUser": u["idUser"], "username": u.get("username", ""), "email": u.get("email", "")} for u in users if u]
                })
            return group_accounts
    
    def get_by_id(self, group_account_id: int) -> Optional[Dict]:
        """Get group account by ID from Neo4j."""
        query = """
        MATCH (ag:AccountGroups {idAccountGroups: $id})
        OPTIONAL MATCH (ag)-[:HAS_MEMBER]->(u:User)
        RETURN ag, collect(u) as users
        """
        with self._get_session() as session:
            result = session.run(query, id=group_account_id)
            record = result.single()
            if record:
                ag = record["ag"]
                users = record["users"]
                return {
                    "idAccountGroups": ag["idAccountGroups"],
                    "name": ag["name"],
                    "max_users": ag.get("max_users", 20),  # Default to 20 if not set
                    "users": [{"idUser": u["idUser"], "username": u.get("username", ""), "email": u.get("email", "")} for u in users if u]
                }
            return None
    
    def create(self, group_account_data: Dict) -> Dict:
        """Create new group account in Neo4j."""
        from backend.validation_boundaries import ACCOUNT_GROUP_BVA
        query = """
        CREATE (ag:AccountGroups {
            idAccountGroups: $idAccountGroups,
            name: $name,
            max_users: $max_users
        })
        RETURN ag
        """
        with self._get_session() as session:
            result = session.run(query, 
                idAccountGroups=group_account_data.get("idAccountGroups"),
                name=group_account_data.get("name"),
                max_users=ACCOUNT_GROUP_BVA.max_users
            )
            record = result.single()
            if record:
                group_account_id = group_account_data.get("idAccountGroups")
                # Handle user association if user_ids is provided
                user_ids = group_account_data.get("user_ids")
                if user_ids:
                    user_query = """
                    MATCH (ag:AccountGroups {idAccountGroups: $group_id}), (u:User)
                    WHERE u.idUser IN $user_ids
                    CREATE (ag)-[:HAS_MEMBER]->(u)
                    """
                    session.run(user_query, group_id=group_account_id, user_ids=user_ids)
                
                return self.get_by_id(group_account_id)
            return group_account_data
    
    def update(self, group_account_id: int, group_account_data: Dict) -> Dict:
        """Update group account in Neo4j."""
        query = """
        MATCH (ag:AccountGroups {idAccountGroups: $id})
        SET ag.name = $name,
            ag.max_users = $max_users
        RETURN ag
        """
        with self._get_session() as session:
            result = session.run(query,
                id=group_account_id,
                name=group_account_data.get("name"),
                max_users=group_account_data.get("max_users")
            )
            record = result.single()
            if record:
                # Handle user association update if user_ids is provided
                user_ids = group_account_data.get("user_ids")
                if user_ids is not None:
                    # Remove existing user relationships
                    delete_query = """
                    MATCH (ag:AccountGroups {idAccountGroups: $group_id})-[r:HAS_MEMBER]-()
                    DELETE r
                    """
                    session.run(delete_query, group_id=group_account_id)
                    
                    # Add new user relationships
                    user_query = """
                    MATCH (ag:AccountGroups {idAccountGroups: $group_id}), (u:User)
                    WHERE u.idUser IN $user_ids
                    CREATE (ag)-[:HAS_MEMBER]->(u)
                    """
                    session.run(user_query, group_id=group_account_id, user_ids=user_ids)
                
                return self.get_by_id(group_account_id)
            raise ValueError(f"Group account {group_account_id} not found")
    
    def delete(self, group_account_id: int) -> bool:
        """Delete group account from Neo4j."""
        query = """
        MATCH (ag:AccountGroups {idAccountGroups: $id})
        DETACH DELETE ag
        """
        with self._get_session() as session:
            result = session.run(query, id=group_account_id)
            return result.consume().counters.nodes_deleted > 0
    
    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None
    ) -> List[Dict]:
        """Search transactions in Neo4j."""
        query = """
        MATCH (a:Account)-[:HAS_TRANSACTION]->(t:Transaction)-[:BELONGS_TO_CATEGORY]->(c:Category)
        WHERE t.description CONTAINS $search_text
        """
        params = {"search_text": search_text}
        
        if start_date:
            query += " AND t.date >= $start_date"
            params["start_date"] = start_date.isoformat()
        if end_date:
            query += " AND t.date <= $end_date"
            params["end_date"] = end_date.isoformat()
        if category_id:
            query += " AND c.idCategory = $category_id"
            params["category_id"] = category_id
        
        query += " RETURN t, c, a ORDER BY t.date DESC LIMIT 1000"
        
        with self._get_session() as session:
            result = session.run(query, **params)
            transactions = []
            for record in result:
                t = record["t"]
                transactions.append({
                    "idTransaction": t["idTransaction"],
                    "amount": t["amount"],
                    "description": t.get("description"),
                    "date": t.get("date"),
                    "type": t["type"]
                })
            return transactions
    
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """Get summary aggregated by category from Neo4j."""
        query = """
        MATCH (t:Transaction)-[:BELONGS_TO_CATEGORY]->(c:Category)
        """
        conditions = []
        params = {}
        
        if start_date:
            conditions.append("t.date >= $start_date")
            params["start_date"] = start_date.isoformat()
        if end_date:
            conditions.append("t.date <= $end_date")
            params["end_date"] = end_date.isoformat()
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += """
        RETURN c.name as category_name, 
               COUNT(t) as count, 
               SUM(t.amount) as total
        ORDER BY total DESC
        """
        
        with self._get_session() as session:
            result = session.run(query, **params)
            summary = {}
            for record in result:
                category_name = record["category_name"]
                summary[category_name] = {
                    "count": record["count"],
                    "total": record["total"]
                }
            return summary