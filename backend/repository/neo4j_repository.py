# backend/repository/neo4j_repository.py
"""
Neo4j repository implementations - Matches MySQL repository structure
"""
from typing import List, Dict, Optional
from datetime import date
from backend.database import get_neo4j_driver
from backend.repository.base_repository import (
    IUserRepository,
    IAccountRepository,
    IBudgetRepository,
    ITransactionRepository,
    ICategoryRepository
)


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
        # Generate ID if not provided (using internal Neo4j ID as fallback)
        if "idUser" not in user_data:
            # Get max ID and increment
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
            MATCH (a:Account)
            WHERE a.User_idUser = $user_id OR EXISTS((:User {idUser: $user_id})-[:OWNS]->(a))
            OPTIONAL MATCH (u:User)-[:OWNS]->(a)
            RETURN a, u
            ORDER BY a.idAccount
            """
            params = {"user_id": user_id}
        else:
            query = """
            MATCH (a:Account)
            OPTIONAL MATCH (u:User)-[:OWNS]->(a)
            RETURN a, u
            ORDER BY a.idAccount
            """
            params = {}
        
        with self._get_session() as session:
            result = session.run(query, **params)
            accounts = []
            for record in result:
                a = record["a"]
                # Brug User_idUser fra account property hvis tilgængelig, ellers fra relation
                user_id_from_account = a.get("User_idUser")
                if not user_id_from_account and "u" in record and record["u"]:
                    user_id_from_account = record["u"].get("idUser")
                accounts.append({
                    "idAccount": a["idAccount"],
                    "name": a["name"],
                    "saldo": float(a.get("saldo", 0.0)),
                    "User_idUser": user_id_from_account
                })
            return accounts
    
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        """Get account by ID from Neo4j."""
        # Brug OPTIONAL MATCH så account findes selv uden OWNS relation
        # Først prøv at finde med relation, ellers find account direkte
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
                # Brug User_idUser fra account property hvis tilgængelig, ellers fra relation
                user_id = a.get("User_idUser")
                if not user_id and "u" in record and record["u"]:
                    user_id = record["u"].get("idUser")
                return {
                    "idAccount": a["idAccount"],
                    "name": a["name"],
                    "saldo": float(a.get("saldo", 0.0)),
                    "User_idUser": user_id
                }
            return None
    
    def create(self, account_data: Dict) -> Dict:
        """Create new account in Neo4j."""
        # Generate ID if not provided
        if "idAccount" not in account_data:
            query_max = "MATCH (a:Account) RETURN MAX(a.idAccount) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                account_data["idAccount"] = max_id + 1
        
        query = """
        MATCH (u:User {idUser: $User_idUser})
        CREATE (a:Account {
            idAccount: $idAccount,
            name: $name,
            saldo: $saldo,
            User_idUser: $User_idUser
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
                User_idUser=account_data.get("User_idUser")
            )
            record = result.single()
            if record:
                return self.get_by_id(account_data["idAccount"])
            return account_data
    
    def update(self, account_id: int, account_data: Dict) -> Dict:
        """Update account in Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $id})
        SET a.name = COALESCE($name, a.name),
            a.saldo = COALESCE($saldo, a.saldo)
        RETURN a
        """
        with self._get_session() as session:
            result = session.run(
                query,
                id=account_id,
                name=account_data.get("name"),
                saldo=account_data.get("saldo")
            )
            record = result.single()
            if record:
                return self.get_by_id(account_id)
            raise ValueError(f"Account {account_id} not found")
    
    def delete(self, account_id: int) -> bool:
        """Delete account from Neo4j."""
        query = """
        MATCH (a:Account {idAccount: $id})
        DETACH DELETE a
        """
        with self._get_session() as session:
            result = session.run(query, id=account_id)
            return result.consume().counters.nodes_deleted > 0


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
                    "amount": float(b.get("amount", 0.0)),
                    "budget_date": _convert_neo4j_date(b.get("budget_date")),
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
                    "amount": float(b.get("amount", 0.0)),
                    "budget_date": _convert_neo4j_date(b.get("budget_date")),
                    "Account_idAccount": record["a"]["idAccount"] if "a" in record else None
                }
            return None
    
    def create(self, budget_data: Dict) -> Dict:
        """Create new budget in Neo4j."""
        # Generate ID if not provided
        if "idBudget" not in budget_data:
            query_max = "MATCH (b:Budget) RETURN MAX(b.idBudget) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                budget_data["idBudget"] = max_id + 1
        
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
            result = session.run(
                query,
                idBudget=budget_data.get("idBudget"),
                amount=budget_data.get("amount"),
                budget_date=budget_data.get("budget_date"),
                Account_idAccount=budget_data.get("Account_idAccount")
            )
            record = result.single()
            if record:
                return self.get_by_id(budget_data["idBudget"])
            return budget_data
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        """Update budget in Neo4j."""
        query = """
        MATCH (b:Budget {idBudget: $id})
        SET b.amount = COALESCE($amount, b.amount),
            b.budget_date = COALESCE($budget_date, b.budget_date)
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
                transactions.append({
                    "idTransaction": t["idTransaction"],
                    "amount": float(t.get("amount", 0.0)),
                    "description": t.get("description"),
                    "date": _convert_neo4j_date(t.get("date")),
                    "type": t.get("type"),
                    "Category_idCategory": record["c"]["idCategory"],
                    "Account_idAccount": record["a"]["idAccount"]
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
                return {
                    "idTransaction": t["idTransaction"],
                    "amount": float(t.get("amount", 0.0)),
                    "description": t.get("description"),
                    "date": _convert_neo4j_date(t.get("date")),
                    "type": t.get("type"),
                    "Category_idCategory": record["c"]["idCategory"],
                    "Account_idAccount": record["a"]["idAccount"]
                }
            return None
    
    def create(self, transaction_data: Dict) -> Dict:
        """Create new transaction in Neo4j."""
        # Generate ID if not provided
        if "idTransaction" not in transaction_data:
            query_max = "MATCH (t:Transaction) RETURN MAX(t.idTransaction) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                transaction_data["idTransaction"] = max_id + 1
        
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
            result = session.run(
                query,
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
        # Delete old relationships
        delete_query = """
        MATCH (t:Transaction {idTransaction: $id})-[r]-()
        DELETE r
        """
        # Update and recreate relationships
        create_query = """
        MATCH (a:Account {idAccount: $Account_idAccount})
        MATCH (c:Category {idCategory: $Category_idCategory})
        MATCH (t:Transaction {idTransaction: $id})
        SET t.amount = COALESCE($amount, t.amount),
            t.description = COALESCE($description, t.description),
            t.date = COALESCE($date, t.date),
            t.type = COALESCE($type, t.type)
        CREATE (a)-[:HAS_TRANSACTION]->(t)
        CREATE (t)-[:BELONGS_TO_CATEGORY]->(c)
        RETURN t
        """
        with self._get_session() as session:
            session.run(delete_query, id=transaction_id)
            session.run(
                create_query,
                id=transaction_id,
                amount=transaction_data.get("amount"),
                description=transaction_data.get("description"),
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
                    "amount": float(t.get("amount", 0.0)),
                    "description": t.get("description"),
                    "date": _convert_neo4j_date(t.get("date")),
                    "type": t.get("type"),
                    "Category_idCategory": record["c"]["idCategory"],
                    "Account_idAccount": record["a"]["idAccount"]
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
                    "total": float(record["total"])
                }
            return summary


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
            return [{
                "idCategory": record["c"]["idCategory"],
                "name": record["c"]["name"],
                "type": record["c"]["type"]
            } for record in result]
    
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
        # Generate ID if not provided
        if "idCategory" not in category_data:
            query_max = "MATCH (c:Category) RETURN MAX(c.idCategory) as max_id"
            with self._get_session() as session:
                result = session.run(query_max)
                record = result.single()
                max_id = record["max_id"] if record and record["max_id"] else 0
                category_data["idCategory"] = max_id + 1
        
        query = """
        CREATE (c:Category {
            idCategory: $idCategory,
            name: $name,
            type: $type
        })
        RETURN c
        """
        with self._get_session() as session:
            result = session.run(
                query,
                idCategory=category_data.get("idCategory"),
                name=category_data.get("name"),
                type=category_data.get("type", "expense")
            )
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
        SET c.name = COALESCE($name, c.name),
            c.type = COALESCE($type, c.type)
        RETURN c
        """
        with self._get_session() as session:
            result = session.run(
                query,
                id=category_id,
                name=category_data.get("name"),
                type=category_data.get("type")
            )
            record = result.single()
            if record:
                c = record["c"]
                return {
                    "idCategory": c["idCategory"],
                    "name": c["name"],
                    "type": c["type"]
                }
            raise ValueError(f"Category {category_id} not found")
    
    def delete(self, category_id: int) -> bool:
        """Delete category from Neo4j."""
        query = """
        MATCH (c:Category {idCategory: $id})
        DETACH DELETE c
        """
        with self._get_session() as session:
            result = session.run(query, id=category_id)
            return result.consume().counters.nodes_deleted > 0

