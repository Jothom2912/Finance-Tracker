"""Domain exceptions for Account bounded context."""


class AccountException(Exception):
    """Base exception for account domain."""

    pass


class AccountNotFound(AccountException):
    """Raised when account is not found."""

    def __init__(self, account_id: int):
        self.account_id = account_id
        super().__init__("Konto ikke fundet.")


class UserNotFoundForAccount(AccountException):
    """Raised when user doesn't exist when creating account."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__("Bruger med dette ID findes ikke.")


class UpstreamServiceUnavailable(AccountException):
    """Raised when a required upstream cannot give a usable answer."""

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        super().__init__(f"{service_name} er midlertidigt utilgængelig.")


class AccountGroupNotFound(AccountException):
    """Raised when account group is not found."""

    def __init__(self, group_id: int):
        self.group_id = group_id
        super().__init__("Kontogruppe ikke fundet.")


class InvalidUserInGroup(AccountException):
    """Raised when one or more user IDs are invalid."""

    def __init__(self) -> None:
        super().__init__("Mindst én bruger ID er ugyldig.")
