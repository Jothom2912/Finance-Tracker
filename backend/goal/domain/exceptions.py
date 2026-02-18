"""
Domain exceptions for Goal bounded context.
These represent business rule violations.
"""


class GoalException(Exception):
    """Base exception for goal domain."""
    pass


class GoalNotFound(GoalException):
    """Raised when goal is not found."""
    def __init__(self, goal_id: int):
        self.goal_id = goal_id
        super().__init__("Mål ikke fundet.")


class AccountNotFoundForGoal(GoalException):
    """Raised when account doesn't exist when creating goal."""
    def __init__(self, account_id: int):
        self.account_id = account_id
        super().__init__("Konto med dette ID findes ikke.")
