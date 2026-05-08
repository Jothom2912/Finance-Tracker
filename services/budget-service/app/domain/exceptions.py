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
