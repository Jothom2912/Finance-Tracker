# backend/repositories/neo4j/user_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IUserRepository

def _convert_neo4j_date(value):
    """Konverter Neo4j date til Python date/string."""
    if value is None:
        return None
    if hasattr(value, 'to_native'):
        return value.to_native()  # Konverterer neo4j.time.Date til datetime.date
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)

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
                "created_at": _convert_neo4j_date(record["u"].get("created_at"))
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
                    "created_at": _convert_neo4j_date(u.get("created_at"))
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
                    "created_at": _convert_neo4j_date(u.get("created_at"))
                }
            return None
    
    def get_by_username_for_auth(self, username: str) -> Optional[Dict]:
        """Get user by username INCLUDING password - kun til authentication."""
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
                    "password": u.get("password"),  # Inkluder password
                    "created_at": _convert_neo4j_date(u.get("created_at"))
                }
            return None
    
    def get_by_email_for_auth(self, email: str) -> Optional[Dict]:
        """Get user by email INCLUDING password - kun til authentication."""
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
                    "password": u.get("password"),
                    "created_at": _convert_neo4j_date(u.get("created_at"))
                }
            return None
    
    def create(self, user_data: Dict) -> Dict:
        """Create new user in Neo4j."""
        # Generate ID if not provided
        if "idUser" not in user_data or user_data.get("idUser") is None:
            query_max = "MATCH (u:User) RETURN MAX(u.idUser) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                user_data["idUser"] = max_id + 1
        
        query = """
        CREATE (u:User {
            idUser: $idUser,
            username: $username,
            email: $email,
            password: $password,
            created_at: $created_at
        })
        RETURN u
        """
        with self._get_session() as session:
            result = session.run(
                query,
                idUser=user_data.get("idUser"),
                username=user_data.get("username"),
                email=user_data.get("email"),
                password=user_data.get("password"),
                created_at=user_data.get("created_at")
            )
            record = result.single()
            if record:
                u = record["u"]
                return {
                    "idUser": u["idUser"],
                    "username": u["username"],
                    "email": u["email"],
                    "created_at": _convert_neo4j_date(u.get("created_at"))
                }
            return user_data
