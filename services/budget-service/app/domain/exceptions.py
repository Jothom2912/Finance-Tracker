class BudgetException(Exception):
    pass


class BudgetNotFound(BudgetException):
    def __init__(self, budget_id: int):
        self.budget_id = budget_id
        super().__init__(f"Budget with ID {budget_id} not found")


class CategoryNotFoundForBudget(BudgetException):
    def __init__(self, category_id: int):
        self.category_id = category_id
        super().__init__(f"Kategori med ID {category_id} findes ikke.")


class AccountRequiredForBudget(BudgetException):
    def __init__(self) -> None:
        super().__init__("Account ID er påkrævet for at oprette et budget.")


class CategoryRequiredForBudget(BudgetException):
    def __init__(self) -> None:
        super().__init__("category_id er påkrævet for at oprette et budget.")


class MonthlyBudgetException(Exception):
    pass


class MonthlyBudgetNotFound(MonthlyBudgetException):
    def __init__(self, budget_id: int = 0, *, month: int = 0, year: int = 0):
        if month and year:
            super().__init__(f"Ingen budget fundet for {month:02d}/{year}.")
        else:
            super().__init__(f"Monthly budget with ID {budget_id} not found")


class MonthlyBudgetAlreadyExists(MonthlyBudgetException):
    def __init__(self, month: int, year: int):
        super().__init__(f"Der findes allerede et budget for {month:02d}/{year}.")


class CategoryNotFoundForBudgetLine(MonthlyBudgetException):
    def __init__(self, category_id: int):
        super().__init__(f"Kategori med ID {category_id} findes ikke.")


class AccountRequiredForMonthlyBudget(MonthlyBudgetException):
    def __init__(self) -> None:
        super().__init__("Account ID er påkrævet.")


class NoBudgetToCopy(MonthlyBudgetException):
    def __init__(self, month: int, year: int):
        super().__init__(f"Ingen budget fundet for {month:02d}/{year} at kopiere fra.")


class MonthlyBudgetAlreadyClosed(MonthlyBudgetException):
    def __init__(self, month: int, year: int):
        super().__init__(f"Budget for {month:02d}/{year} er allerede lukket.")


class UpstreamServiceUnavailable(Exception):
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"{service_name} er ikke tilgængelig i øjeblikket. Prøv igen senere.")
