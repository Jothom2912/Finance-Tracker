# backend/repositories/neo4j/user_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IUserRepository

class Neo4jUserRepository(IUserRepository):
    """Neo4j implementation of user repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(self) -> List[Dict]:
        """Get all users from Neo4j."""
        query = "MATCH (u:User) RETURN u ORDER BY u.idUser"
        with self._get_session() as session:
            result = session.run(query)
            return [{
                "idUser": record["u"]["idUser"],
                "username": record["u"]["username"],
                "email": record["u"]["email"],
                "created_at": record["u"].get("created_at")
            } for record in result]
    
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID from Neo4j."""
        query = "MATCH (u:User {idUser: $id}) RETURN u"
        with self._get_session() as session:
            result = session.run(query, id=user_id)
            record = result.single()
            if record:
                u = record["u"]
                return {
                    "idUser": u["idUser"],
                    "username": u["username"],
                    "email": u["email"],
                    "created_at": u.get("created_at")
                }
            return None
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username from Neo4j."""
        query = "MATCH (u:User {username: $username}) RETURN u"
        with self._get_session() as session:
            result = session.run(query, username=username)
            record = result.single()
            if record:
                u = record["u"]
                return {
                    "idUser": u["idUser"],
                    "username": u["username"],
                    "email": u["email"],
                    "created_at": u.get("created_at")
                }
            return None
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email from Neo4j."""
        query = "MATCH (u:User {email: $email}) RETURN u"
        with self._get_session() as session:
            result = session.run(query, email=email)
            record = result.single()
            if record:
                u = record["u"]
                return {
                    "idUser": u["idUser"],
                    "username": u["username"],
                    "email": u["email"],
                    "created_at": u.get("created_at")
                }
            return None
    
    def create(self, user_data: Dict) -> Dict:
        """Create new user in Neo4j."""
        query = """
        CREATE (u:User {
            idUser: $idUser,
            username: $username,
            email: $email,
            created_at: $created_at
        })
        RETURN u
        """
        with self._get_session() as session:
            result = session.run(query, **user_data)
            record = result.single()
            if record:
                u = record["u"]
                return {
                    "idUser": u["idUser"],
                    "username": u["username"],
                    "email": u["email"],
                    "created_at": u.get("created_at")
                }
            return user_data
    
    def authenticate_user(self, username_or_email: str) -> Optional[Dict]:
        """Get user data including password for authentication."""
        # Neo4j doesn't store passwords for security reasons
        return None

