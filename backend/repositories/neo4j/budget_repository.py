# backend/repositories/neo4j/budget_repository.py
from typing import List, Dict, Optional
from backend.database.neo4j import get_neo4j_driver
from backend.repositories.base import IBudgetRepository

def _convert_neo4j_date(value):
    """Konverter Neo4j date til Python date/string."""
    if value is None:
        return None
    if hasattr(value, 'to_native'):
        return value.to_native()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)

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
        """Get all budgets from Neo4j with category info, optionally filtered by account_id."""
        if account_id:
            query = """
            MATCH (a:Account {idAccount: $account_id})-[:HAS_BUDGET]->(b:Budget)
            OPTIONAL MATCH (b)-[:FOR_CATEGORY]->(c:Category)
            RETURN b, a, c
            ORDER BY b.idBudget
            """
            params = {"account_id": account_id}
        else:
            query = """
            MATCH (b:Budget)
            OPTIONAL MATCH (b)-[:FOR_CATEGORY]->(c:Category)
            RETURN b, c
            ORDER BY b.idBudget
            """
            params = {}
        
        with self._get_session() as session:
            result = session.run(query, **params)
            budgets = []
            for record in result:
                b = record["b"]
                c = record.get("c")
                budgets.append({
                    "idBudget": b["idBudget"],
                    "amount": float(b.get("amount", 0.0)),
                    "budget_date": _convert_neo4j_date(b.get("budget_date")),
                    "Account_idAccount": record.get("a", {}).get("idAccount") if "a" in record else None,
                    "Category_idCategory": c["idCategory"] if c else b.get("Category_idCategory")
                })
            return budgets
    
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        """Get budget by ID from Neo4j with category."""
        query = """
        MATCH (a:Account)-[:HAS_BUDGET]->(b:Budget {idBudget: $id})
        OPTIONAL MATCH (b)-[:FOR_CATEGORY]->(c:Category)
        RETURN b, a, c
        """
        with self._get_session() as session:
            result = session.run(query, id=budget_id)
            record = result.single()
            if record:
                b = record["b"]
                c = record.get("c")
                return {
                    "idBudget": b["idBudget"],
                    "amount": float(b.get("amount", 0.0)),
                    "budget_date": _convert_neo4j_date(b.get("budget_date")),
                    "Account_idAccount": record["a"]["idAccount"] if "a" in record else None,
                    "Category_idCategory": c["idCategory"] if c else b.get("Category_idCategory")
                }
            return None
    
    def create(self, budget_data: Dict) -> Dict:
        """Create new budget in Neo4j with category relationship."""
        # Generate ID if not provided
        if "idBudget" not in budget_data or budget_data.get("idBudget") is None:
            query_max = "MATCH (b:Budget) RETURN COALESCE(MAX(b.idBudget), 0) + 1 as next_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                budget_data["idBudget"] = record["next_id"] if record and record["next_id"] else 1
        
        # Get Category_idCategory from budget_data
        category_id = budget_data.get("Category_idCategory") or budget_data.get("category_id")
        
        query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        MATCH (c:Category {idCategory: $Category_idCategory})
        CREATE (b:Budget {
            idBudget: $idBudget,
            amount: $amount,
            budget_date: $budget_date,
            Category_idCategory: $Category_idCategory
        })
        CREATE (a)-[:HAS_BUDGET]->(b)
        CREATE (b)-[:FOR_CATEGORY]->(c)
        RETURN b, a, c
        """
        with self._get_session() as session:
            result = session.run(
                query,
                idBudget=budget_data.get("idBudget"),
                amount=budget_data.get("amount"),
                budget_date=budget_data.get("budget_date"),
                Account_idAccount=budget_data.get("Account_idAccount"),
                Category_idCategory=category_id
            )
            record = result.single()
            if record:
                return self.get_by_id(budget_data["idBudget"])
            return budget_data
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        """Update budget in Neo4j, including category relationship if changed."""
        # Get Category_idCategory from budget_data
        category_id = budget_data.get("Category_idCategory") or budget_data.get("category_id")
        
        # First, update basic properties
        update_query = """
        MATCH (b:Budget {idBudget: $id})
        SET b.amount = COALESCE($amount, b.amount),
            b.budget_date = COALESCE($budget_date, b.budget_date)
        """
        
        # If category_id is provided, update the relationship
        if category_id is not None:
            # Delete old category relationship
            delete_rel_query = """
            MATCH (b:Budget {idBudget: $id})-[r:FOR_CATEGORY]->()
            DELETE r
            """
            # Create new category relationship
            create_rel_query = """
            MATCH (b:Budget {idBudget: $id})
            MATCH (c:Category {idCategory: $Category_idCategory})
            CREATE (b)-[:FOR_CATEGORY]->(c)
            SET b.Category_idCategory = $Category_idCategory
            """
        
        with self._get_session() as session:
            # Update basic properties
            session.run(
                update_query,
                id=budget_id,
                amount=budget_data.get("amount"),
                budget_date=budget_data.get("budget_date")
            )
            
            # Update category relationship if provided
            if category_id is not None:
                session.run(delete_rel_query, id=budget_id)
                session.run(create_rel_query, id=budget_id, Category_idCategory=category_id)
            
            return self.get_by_id(budget_id) or budget_data
    
    def delete(self, budget_id: int) -> bool:
        """Delete budget from Neo4j."""
        query = """
        MATCH (b:Budget {idBudget: $id})
        DETACH DELETE b
        """
        with self._get_session() as session:
            result = session.run(query, id=budget_id)
            return result.consume().counters.nodes_deleted > 0
