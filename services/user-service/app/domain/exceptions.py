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


class CurrentPasswordIncorrectException(UserException):
    """Det oplyste nuværende password matchede ikke — mappes til 403.

    Bevidst IKKE ``InvalidCredentialsException``, selvom fejlen ligner
    den. Den mapper til 401, og frontendens apiClient kalder
    ``handleUnauthorized()`` på enhver 401 fra en ikke-auth-rute
    (``apiClient.jsx:51-61``): den rydder auth-storage og redirecter til
    /login. Et forkert nuværende password ville altså logge brugeren ud
    i stedet for at vise en fejl i formularen. 403 siger det rigtige —
    du ER autentificeret, men denne handling blev afvist.
    """

    def __init__(self) -> None:
        super().__init__("Current password is incorrect.")
