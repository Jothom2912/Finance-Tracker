"""
Domain exceptions for User bounded context.
These represent business rule violations.
"""


class UserException(Exception):
    """Base exception for user domain."""
    pass


class UserNotFound(UserException):
    """Raised when user is not found."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__("Bruger ikke fundet.")


class DuplicateEmail(UserException):
    """Raised when email already exists."""
    def __init__(self, email: str):
        self.email = email
        super().__init__("Bruger med denne e-mail eksisterer allerede.")


class DuplicateUsername(UserException):
    """Raised when username already exists."""
    def __init__(self, username: str):
        self.username = username
        super().__init__("Brugernavn er allerede taget.")


class InvalidCredentials(UserException):
    """Raised when login credentials are wrong."""
    def __init__(self) -> None:
        super().__init__("Forkert adgangskode.")


class UserOrEmailNotFound(UserException):
    """Raised when username/email not found during login."""
    def __init__(self) -> None:
        super().__init__("Brugernavn eller email ikke fundet.")
