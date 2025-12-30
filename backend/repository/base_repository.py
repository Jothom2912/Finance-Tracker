# backend/repository/base_repository.py
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
    def create(self, name: str) -> Dict:
        """Create new category."""
        pass
    
    @abstractmethod
    def delete(self, category_id: int) -> bool:
        """Delete category."""
        pass

class IBudgetRepository(ABC):
    
    @abstractmethod
    def getall(self) -> List[Dict]:
        """ get all budgets """
        pass
    
    @abstractmethod
    def getOne(self) ->  Optional[Dict]:
        """get one budget"""
        pass
    
    @abstractmethod
    def Delete(self,budget_id: int) -> bool:
        """delete one budget """
        pass
    
    @abstractmethod
    def Create(self) -> Dict:
        """create one budget """
        pass
    
    @abstractmethod
    def update(self,budget_id: int) -> Dict:
        """ update one budget """
        
class IGoalRepository(ABC):
    
    @abstractmethod
    def getall(self) -> List[Dict]:
        """ get all goals """
        pass
    
    @abstractmethod
    def getOne(self,goal_id: int) ->  Optional[Dict]:
        """get one goal"""
        pass
    
    @abstractmethod
    def Delete(self,goal_id: int) -> bool:
        """delete one goal """
        pass
    
    @abstractmethod
    def Create(self) -> Dict:
        """create one goal """
        pass
    
    @abstractmethod
    def update(self,goal_id: int) -> Dict:
        """ update one goal """
        
class IUserRepository(ABC):
    
    @abstractmethod
    def getall(self) -> List[Dict]:
        """ get all users """
        pass
    
    @abstractmethod
    def getOne(self,user_id: int) -> Optional[Dict]:
        """get one user"""
        pass
    
    @abstractmethod
    def Delete(self,user_id: int) -> bool:
        """delete one user """
        pass
    
    @abstractmethod
    def Create(self) -> Dict:
        """create one user """
        pass
    
    @abstractmethod
    def update(self,user_id: int) -> Dict:
        """ update one user """
        
class IAccountRepository(ABC):
    
    @abstractmethod
    def getall(self) -> Dict:
        """ get all accounts """
        pass
    
    @abstractmethod
    def getOne(self,account_id: int) ->  Optional[Dict]:
        """get one account"""
        pass
    
    @abstractmethod
    def Delete(self,account_id: int) -> bool:
        """delete one account """
        pass
    
    @abstractmethod
    def Create(self) -> Dict:
        """create one account """
        pass
    
    @abstractmethod
    def update(self,account_id: int) -> Dict:
        """ update one account """
        
        
        
