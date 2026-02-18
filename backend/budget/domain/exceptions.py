"""
Domain exceptions for Budget bounded context.
These represent business rule violations.
"""


class BudgetException(Exception):
    """Base exception for budget domain."""
    pass


class BudgetNotFound(BudgetException):
    """Raised when a budget is not found."""
    def __init__(self, budget_id: int):
        self.budget_id = budget_id
        super().__init__(f"Budget with ID {budget_id} not found")


class CategoryNotFoundForBudget(BudgetException):
    """Raised when category doesn't exist when creating/updating budget."""
    def __init__(self, category_id: int):
        self.category_id = category_id
        super().__init__(f"Kategori med ID {category_id} findes ikke.")


class AccountRequiredForBudget(BudgetException):
    """Raised when account ID is missing."""
    def __init__(self) -> None:
        super().__init__("Account ID er påkrævet for at oprette et budget.")


class CategoryRequiredForBudget(BudgetException):
    """Raised when category ID is missing."""
    def __init__(self) -> None:
        super().__init__("category_id er påkrævet for at oprette et budget.")
