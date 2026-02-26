"""
Domain exceptions for MonthlyBudget bounded context.
"""


class MonthlyBudgetException(Exception):
    """Base exception for monthly budget domain."""


class MonthlyBudgetNotFound(MonthlyBudgetException):
    def __init__(self, budget_id: int):
        super().__init__(f"Monthly budget with ID {budget_id} not found")


class MonthlyBudgetAlreadyExists(MonthlyBudgetException):
    def __init__(self, month: int, year: int):
        super().__init__(
            f"Der findes allerede et budget for {month:02d}/{year}."
        )


class CategoryNotFoundForBudgetLine(MonthlyBudgetException):
    def __init__(self, category_id: int):
        super().__init__(f"Kategori med ID {category_id} findes ikke.")


class AccountRequiredForMonthlyBudget(MonthlyBudgetException):
    def __init__(self) -> None:
        super().__init__("Account ID er påkrævet.")


class NoBudgetToCopy(MonthlyBudgetException):
    def __init__(self, month: int, year: int):
        super().__init__(
            f"Ingen budget fundet for {month:02d}/{year} at kopiere fra."
        )
