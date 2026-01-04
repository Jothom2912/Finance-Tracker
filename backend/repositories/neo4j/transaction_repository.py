# backend/repositories/neo4j/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import ITransactionRepository

def _convert_neo4j_date(value):
    """Konverter Neo4j date til Python date/string."""
    if value is None:
        return None
    if hasattr(value, 'to_native'):
        return value.to_native()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)

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
                # Convert date to date object
                date_value = _convert_neo4j_date(t.get("date"))
                if isinstance(date_value, str):
                    from datetime import datetime
                    try:
                        date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
                    except:
                        date_value = None
                
                transactions.append({
                    "idTransaction": t["idTransaction"],
                    "amount": t["amount"],
                    "description": t.get("description"),
                    "date": date_value,  # Use 'date' consistently
                    "type": t["type"],
                    "Category_idCategory": c["idCategory"],
                    "category_name": c["name"],
                    "Account_idAccount": a["idAccount"],
                    "account_name": a["name"],
                    "created_at": _convert_neo4j_date(t.get("created_at"))
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
                # Convert date to date object
                date_value = _convert_neo4j_date(t.get("date"))
                if isinstance(date_value, str):
                    from datetime import datetime
                    try:
                        date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
                    except:
                        date_value = None
                
                return {
                    "idTransaction": t["idTransaction"],
                    "amount": t["amount"],
                    "description": t.get("description"),
                    "date": date_value,  # Use 'date' consistently
                    "type": t["type"],
                    "Category_idCategory": c["idCategory"],
                    "category_name": c["name"],
                    "Account_idAccount": a["idAccount"],
                    "account_name": a["name"],
                    "created_at": _convert_neo4j_date(t.get("created_at"))
                }
            return None
    
    def create(self, transaction_data: Dict) -> Dict:
        """Create new transaction in Neo4j - håndter date korrekt og generer ID automatisk."""
        # ✅ Generer unikt ID hvis ikke allerede sat
        transaction_id = transaction_data.get("idTransaction")
        if transaction_id is None:
            # Hent højeste eksisterende ID og inkrementer
            with self._get_session() as session:
                result = session.run("MATCH (t:Transaction) RETURN COALESCE(MAX(t.idTransaction), 0) + 1 AS next_id")
                record = result.single()
                transaction_id = record["next_id"] if record and record["next_id"] else 1
        
        # Håndter date - konverter til ISO string hvis det er date objekt
        date_value = transaction_data.get("date")
        if date_value is None:
            date_value = date.today().isoformat()
        elif isinstance(date_value, date):
            date_value = date_value.isoformat()
        elif hasattr(date_value, 'isoformat'):
            date_value = date_value.isoformat()
        
        # Ensure created_at is set and convert to ISO string if needed
        created_at = transaction_data.get("created_at")
        if created_at is None:
            from datetime import datetime
            created_at = datetime.now().isoformat()
        elif hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        
        query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        MATCH (c:Category {idCategory: $Category_idCategory})
        CREATE (t:Transaction {
            idTransaction: $idTransaction,
            amount: $amount,
            description: $description,
            date: $date,
            type: $type,
            created_at: $created_at
        })
        CREATE (a)-[:HAS_TRANSACTION]->(t)
        CREATE (t)-[:BELONGS_TO_CATEGORY]->(c)
        RETURN t, c, a
        """
        with self._get_session() as session:
            result = session.run(query, 
                idTransaction=transaction_id,  # ✅ Brug genereret ID
                amount=transaction_data.get("amount"),
                description=transaction_data.get("description", ""),
                date=date_value,  # ✅ BRUG "date" konsistent
                type=transaction_data.get("type"),
                created_at=created_at,
                Account_idAccount=transaction_data.get("Account_idAccount"),
                Category_idCategory=transaction_data.get("Category_idCategory")
            )
            record = result.single()
            if record:
                return self.get_by_id(transaction_id)  # ✅ Brug genereret ID
            return transaction_data
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        """Update transaction in Neo4j - håndter date korrekt."""
        # Håndter date - konverter til ISO string hvis det er date objekt
        date_value = transaction_data.get("date")
        if date_value and isinstance(date_value, date):
            date_value = date_value.isoformat()
        elif date_value and hasattr(date_value, 'isoformat'):
            date_value = date_value.isoformat()
        
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
            # Note: created_at is not updated on update - it should remain the original creation time
            session.run(create_query,
                id=transaction_id,
                amount=transaction_data.get("amount"),
                description=transaction_data.get("description", ""),
                date=date_value,  # ✅ BRUG "date" konsistent
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
                # Convert date to date object
                date_value = _convert_neo4j_date(t.get("date"))
                if isinstance(date_value, str):
                    from datetime import datetime
                    try:
                        date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
                    except:
                        date_value = None
                
                transactions.append({
                    "idTransaction": t["idTransaction"],
                    "amount": t["amount"],
                    "description": t.get("description"),
                    "date": date_value,  # Use 'date' consistently
                    "type": t["type"],
                    "created_at": _convert_neo4j_date(t.get("created_at"))
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

