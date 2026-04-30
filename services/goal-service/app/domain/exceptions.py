class AccountNotFoundForGoal(Exception):
    def __init__(self, account_id: int) -> None:
        super().__init__(f"Account {account_id} not found")
