from __future__ import annotations


class UserException(Exception):
    """Base exception for the user domain."""


class UserNotFoundException(UserException):
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f"User with id {user_id} not found.")


class UserAlreadyExistsException(UserException):
    def __init__(self, field: str, value: str) -> None:
        self.field = field
        self.value = value
        super().__init__(f"User with {field} '{value}' already exists.")


class InvalidCredentialsException(UserException):
    def __init__(self) -> None:
        super().__init__("Invalid email or password.")
