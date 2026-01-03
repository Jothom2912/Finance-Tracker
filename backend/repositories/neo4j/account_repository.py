# backend/repositories/neo4j/account_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IAccountRepository

class Neo4jAccountRepository(IAccountRepository):
    """Neo4j implementation of account repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get all accounts from Neo4j, optionally filtered by user_id."""
        if user_id:
            query = """
            MATCH (u:User {idUser: $user_id})-[:OWNS]->(a:Account)
            RETURN a, u
            ORDER BY a.idAccount
            """
            params = {"user_id": user_id}
        else:
            query = "MATCH (a:Account) RETURN a ORDER BY a.idAccount"
            params = {}
        
        with self._get_session() as session:
            result = session.run(query, **params)
            accounts = []
            for record in result:
                a = record["a"]
                accounts.append({
                    "idAccount": a["idAccount"],
                    "name": a["name"],
                    "saldo": a["saldo"],
                    "User_idUser": record.get("u", {}).get("idUser") if "u" in record else None
                })
            return accounts
    
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        """Get account by ID from Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $id})
        OPTIONAL MATCH (u:User)-[:OWNS]->(a)
        RETURN a, u
        """
        with self._get_session() as session:
            result = session.run(query, id=account_id)
            record = result.single()
            if record:
                a = record["a"]
                return {
                    "idAccount": a["idAccount"],
                    "name": a["name"],
                    "saldo": float(a.get("saldo", 0.0)),
                    "User_idUser": a.get("User_idUser") or (record["u"]["idUser"] if "u" in record and record["u"] else None)
                }
            return None
    
    def create(self, account_data: Dict) -> Dict:
        """Create new account in Neo4j."""
        # Generate ID if not provided
        if "idAccount" not in account_data or account_data.get("idAccount") is None:
            query_max = "MATCH (a:Account) RETURN MAX(a.idAccount) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                account_data["idAccount"] = max_id + 1
        
        # Store User_idUser as property on Account node for easier querying
        user_id = account_data.get("User_idUser") or account_data.get("user_id")
        query = """
        MATCH (u:User {idUser: $user_id})
        CREATE (a:Account {
            idAccount: $idAccount,
            name: $name,
            saldo: $saldo,
            User_idUser: $user_id
        })
        CREATE (u)-[:OWNS]->(a)
        RETURN a, u
        """
        with self._get_session() as session:
            result = session.run(
                query,
                idAccount=account_data.get("idAccount"),
                name=account_data.get("name"),
                saldo=account_data.get("saldo", 0.0),
                user_id=user_id
            )
            record = result.single()
            if record:
                return self.get_by_id(account_data["idAccount"])
            return account_data
    
    def update(self, account_id: int, account_data: Dict) -> Dict:
        """Update account in Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $id})
        SET a.name = $name, a.saldo = $saldo
        RETURN a
        """
        with self._get_session() as session:
            result = session.run(query, id=account_id, **account_data)
            record = result.single()
            if record:
                return self.get_by_id(account_id)
            return account_data
    
    def delete(self, account_id: int) -> bool:
        """Delete account from Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $id})
        DETACH DELETE a
        """
        with self._get_session() as session:
            result = session.run(query, id=account_id)
            return result.consume().counters.nodes_deleted > 0

