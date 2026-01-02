# backend/repositories/base.py
"""
Base repository interfaces - Definerer kontrakter for alle repositories
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import date

class ITransactionRepository(ABC):
    """Abstract interface for transaction repository."""
    
    @abstractmethod
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get transactions with optional filters."""
        pass
    
    @abstractmethod
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        """Get single transaction by ID."""
        pass
    
    @abstractmethod
    def create(self, transaction_data: Dict) -> Dict:
        """Create new transaction."""
        pass
    
    @abstractmethod
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        """Update transaction."""
        pass
    
    @abstractmethod
    def delete(self, transaction_id: int) -> bool:
        """Delete transaction."""
        pass
    
    @abstractmethod
    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None
    ) -> List[Dict]:
        """Search transactions."""
        pass
    
    @abstractmethod
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """Get summary aggregated by category."""
        pass


class ICategoryRepository(ABC):
    """Abstract interface for category repository."""
    
    @abstractmethod
    def get_all(self) -> List[Dict]:
        """Get all categories."""
        pass
    
    @abstractmethod
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        """Get category by ID."""
        pass
    
    @abstractmethod
    def create(self, category_data: Dict) -> Dict:
        """Create new category."""
        pass
    
    @abstractmethod
    def update(self, category_id: int, category_data: Dict) -> Dict:
        """Update category."""
        pass
    
    @abstractmethod
    def delete(self, category_id: int) -> bool:
        """Delete category."""
        pass


class IAccountRepository(ABC):
    """Abstract interface for account repository."""
    
    @abstractmethod
    def get_all(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get all accounts, optionally filtered by user_id."""
        pass
    
    @abstractmethod
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        """Get account by ID."""
        pass
    
    @abstractmethod
    def create(self, account_data: Dict) -> Dict:
        """Create new account."""
        pass
    
    @abstractmethod
    def update(self, account_id: int, account_data: Dict) -> Dict:
        """Update account."""
        pass
    
    @abstractmethod
    def delete(self, account_id: int) -> bool:
        """Delete account."""
        pass


class IUserRepository(ABC):
    """Abstract interface for user repository."""
    
    @abstractmethod
    def get_all(self) -> List[Dict]:
        """Get all users."""
        pass
    
    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    def get_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        pass
    
    @abstractmethod
    def create(self, user_data: Dict) -> Dict:
        """Create new user."""
        pass


class IBudgetRepository(ABC):
    """Abstract interface for budget repository."""
    
    @abstractmethod
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all budgets, optionally filtered by account_id."""
        pass
    
    @abstractmethod
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        """Get budget by ID."""
        pass
    
    @abstractmethod
    def create(self, budget_data: Dict) -> Dict:
        """Create new budget."""
        pass
    
    @abstractmethod
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        """Update budget."""
        pass
    
    @abstractmethod
    def delete(self, budget_id: int) -> bool:
        """Delete budget."""
        pass


class IGoalRepository(ABC):
    """Abstract interface for goal repository."""
    
    @abstractmethod
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all goals, optionally filtered by account_id."""
        pass
    
    @abstractmethod
    def get_by_id(self, goal_id: int) -> Optional[Dict]:
        """Get goal by ID."""
        pass
    
    @abstractmethod
    def create(self, goal_data: Dict) -> Dict:
        """Create new goal."""
        pass
    
    @abstractmethod
    def update(self, goal_id: int, goal_data: Dict) -> Dict:
        """Update goal."""
        pass
    
    @abstractmethod
    def delete(self, goal_id: int) -> bool:
        """Delete goal."""
        pass
    
class IPlannedTransaction(ABC):
    """Abstract interface for planned transaction repository."""

    @abstractmethod
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all planned transactions, optionally filtered by account_id."""
        pass
    
    @abstractmethod
    def get_by_id(self, planned_transaction_id: int) -> Optional[Dict]:
        """Get planned transaction by ID."""
        pass
    
    @abstractmethod
    def create(self, planned_transaction_data: Dict) -> Dict:
        """Create new planned transaction."""
        pass
    
    @abstractmethod
    def update(self, planned_transaction_id: int, planned_transaction_data: Dict) -> Dict:
        """Update planned transaction."""
        pass
    
    @abstractmethod
    def delete(self, planned_transaction_id: int) -> bool:
        """Delete planned transaction."""
        pass


class IGroupAccountRepository(ABC):
    """Abstract interface for group account repository."""

    @abstractmethod
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        """Get all group accounts, optionally filtered by account_id."""
        pass
    
    @abstractmethod
    def get_by_id(self, group_account_id: int) -> Optional[Dict]:
        """Get group account by ID."""
        pass
    
    @abstractmethod
    def create(self, group_account_data: Dict) -> Dict:
        """Create new group account."""
        pass
    
    @abstractmethod
    def update(self, group_account_id: int, group_account_data: Dict) -> Dict:
        """Update group account."""
        pass
    
    @abstractmethod
    def delete(self, group_account_id: int) -> bool:
        """Delete group account."""
        pass


