class AccountNotFoundForGoal(Exception):
    def __init__(self, account_id: int) -> None:
        super().__init__(f"Account {account_id} not found")


class NotAccountOwner(Exception):
    def __init__(self) -> None:
        super().__init__("User does not own the requested account")


class UpstreamServiceUnavailable(Exception):
    def __init__(self, service_name: str) -> None:
        super().__init__(f"{service_name} is unavailable")
