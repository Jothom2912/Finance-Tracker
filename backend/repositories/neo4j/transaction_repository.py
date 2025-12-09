# backend/repositories/neo4j/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import ITransactionRepository

class Neo4jTransactionRepository(ITransactionRepository):
    """Neo4j implementation of transaction repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get transactions from Neo4j with optional filters."""
        query = "MATCH (a:Account)-[:HAS_TRANSACTION]->(t:Transaction)-[:BELONGS_TO_CATEGORY]->(c:Category)"
        conditions = []
        params = {}
        
        if account_id:
            conditions.append("a.idAccount = $account_id")
            params["account_id"] = account_id
        if category_id:
            conditions.append("c.idCategory = $category_id")
            params["category_id"] = category_id
        if start_date:
            conditions.append("t.date >= $start_date")
            params["start_date"] = start_date.isoformat()
        if end_date:
            conditions.append("t.date <= $end_date")
            params["end_date"] = end_date.isoformat()
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " RETURN t, c, a ORDER BY t.date DESC SKIP $offset LIMIT $limit"
        params["offset"] = offset
        params["limit"] = limit
        
        with self._get_session() as session:
            result = session.run(query, **params)
            transactions = []
            for record in result:
                t = record["t"]
                c = record["c"]
                a = record["a"]
                transactions.append({
                    "idTransaction": t["idTransaction"],
                    "amount": t["amount"],
                    "description": t.get("description"),
                    "date": t.get("date"),
                    "type": t["type"],
                    "Category_idCategory": c["idCategory"],
                    "category_name": c["name"],
                    "Account_idAccount": a["idAccount"],
                    "account_name": a["name"]
                })
            return transactions
    
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        """Get single transaction by ID from Neo4j."""
        query = """
        MATCH (a:Account)-[:HAS_TRANSACTION]->(t:Transaction {idTransaction: $id})-[:BELONGS_TO_CATEGORY]->(c:Category)
        RETURN t, c, a
        """
        with self._get_session() as session:
            result = session.run(query, id=transaction_id)
            record = result.single()
            if record:
                t = record["t"]
                c = record["c"]
                a = record["a"]
                return {
                    "idTransaction": t["idTransaction"],
                    "amount": t["amount"],
                    "description": t.get("description"),
                    "date": t.get("date"),
                    "type": t["type"],
                    "Category_idCategory": c["idCategory"],
                    "category_name": c["name"],
                    "Account_idAccount": a["idAccount"],
                    "account_name": a["name"]
                }
            return None
    
    def create(self, transaction_data: Dict) -> Dict:
        """Create new transaction in Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        MATCH (c:Category {idCategory: $Category_idCategory})
        CREATE (t:Transaction {
            idTransaction: $idTransaction,
            amount: $amount,
            description: $description,
            date: $date,
            type: $type
        })
        CREATE (a)-[:HAS_TRANSACTION]->(t)
        CREATE (t)-[:BELONGS_TO_CATEGORY]->(c)
        RETURN t, c, a
        """
        with self._get_session() as session:
            result = session.run(query, 
                idTransaction=transaction_data.get("idTransaction"),
                amount=transaction_data.get("amount"),
                description=transaction_data.get("description", ""),
                date=transaction_data.get("date"),
                type=transaction_data.get("type"),
                Account_idAccount=transaction_data.get("Account_idAccount"),
                Category_idCategory=transaction_data.get("Category_idCategory")
            )
            record = result.single()
            if record:
                return self.get_by_id(transaction_data.get("idTransaction"))
            return transaction_data
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        """Update transaction in Neo4j."""
        # Neo4j update - slet gamle relationships og opret nye
        delete_query = """
        MATCH (t:Transaction {idTransaction: $id})-[r]-()
        DELETE r
        """
        create_query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        MATCH (c:Category {idCategory: $Category_idCategory})
        MATCH (t:Transaction {idTransaction: $id})
        SET t.amount = $amount,
            t.description = $description,
            t.date = $date,
            t.type = $type
        CREATE (a)-[:HAS_TRANSACTION]->(t)
        CREATE (t)-[:BELONGS_TO_CATEGORY]->(c)
        RETURN t
        """
        with self._get_session() as session:
            session.run(delete_query, id=transaction_id)
            session.run(create_query,
                id=transaction_id,
                amount=transaction_data.get("amount"),
                description=transaction_data.get("description", ""),
                date=transaction_data.get("date"),
                type=transaction_data.get("type"),
                Account_idAccount=transaction_data.get("Account_idAccount"),
                Category_idCategory=transaction_data.get("Category_idCategory")
            )
            return self.get_by_id(transaction_id) or transaction_data
    
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction from Neo4j."""
        query = """
        MATCH (t:Transaction {idTransaction: $id})
        DETACH DELETE t
        """
        with self._get_session() as session:
            result = session.run(query, id=transaction_id)
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

