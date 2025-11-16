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
