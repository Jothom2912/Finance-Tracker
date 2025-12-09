# backend/repositories/neo4j/budget_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IBudgetRepository

class Neo4jBudgetRepository(IBudgetRepository):
    """Neo4j implementation of budget repository."""
    
    def __init__(self, driver=None):
        if driver is None:
            self.driver = get_neo4j_driver()
        else:
            self.driver = driver
    
    def _get_session(self):
        """Get Neo4j session"""
        return self.driver.session()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all budgets from Neo4j, optionally filtered by account_id."""
        if account_id:
            query = """
            MATCH (a:Account {idAccount: $account_id})-[:HAS_BUDGET]->(b:Budget)
            RETURN b, a
            ORDER BY b.idBudget
            """
            params = {"account_id": account_id}
        else:
            query = "MATCH (b:Budget) RETURN b ORDER BY b.idBudget"
            params = {}
        
        with self._get_session() as session:
            result = session.run(query, **params)
            budgets = []
            for record in result:
                b = record["b"]
                budgets.append({
                    "idBudget": b["idBudget"],
                    "amount": b["amount"],
                    "budget_date": b.get("budget_date"),
                    "Account_idAccount": record.get("a", {}).get("idAccount") if "a" in record else None
                })
            return budgets
    
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        """Get budget by ID from Neo4j."""
        query = """
        MATCH (a:Account)-[:HAS_BUDGET]->(b:Budget {idBudget: $id})
        RETURN b, a
        """
        with self._get_session() as session:
            result = session.run(query, id=budget_id)
            record = result.single()
            if record:
                b = record["b"]
                return {
                    "idBudget": b["idBudget"],
                    "amount": b["amount"],
                    "budget_date": b.get("budget_date"),
                    "Account_idAccount": record["a"]["idAccount"] if "a" in record else None
                }
            return None
    
    def create(self, budget_data: Dict) -> Dict:
        """Create new budget in Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        CREATE (b:Budget {
            idBudget: $idBudget,
            amount: $amount,
            budget_date: $budget_date
        })
        CREATE (a)-[:HAS_BUDGET]->(b)
        RETURN b, a
        """
        with self._get_session() as session:
            result = session.run(query, **budget_data)
            record = result.single()
            if record:
                return self.get_by_id(budget_data["idBudget"])
            return budget_data
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        """Update budget in Neo4j."""
        query = """
        MATCH (b:Budget {idBudget: $id})
        SET b.amount = $amount,
            b.budget_date = $budget_date
        RETURN b
        """
        with self._get_session() as session:
            result = session.run(
                query,
                id=budget_id,
                amount=budget_data.get("amount"),
                budget_date=budget_data.get("budget_date")
            )
            record = result.single()
            if record:
                return self.get_by_id(budget_id)
            raise ValueError(f"Budget {budget_id} not found")
    
    def delete(self, budget_id: int) -> bool:
        """Delete budget from Neo4j."""
        query = """
        MATCH (b:Budget {idBudget: $id})
        DETACH DELETE b
        """
        with self._get_session() as session:
            result = session.run(query, id=budget_id)
            return result.consume().counters.nodes_deleted > 0

