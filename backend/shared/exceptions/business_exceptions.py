# backend/shared/exceptions/business_exceptions.py
"""
Custom Business Exceptions
"""
from fastapi import HTTPException, status


class BusinessException(HTTPException):
    """Base exception for business logic errors."""
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class ValidationException(BusinessException):
    """Raised when validation fails."""
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class NotFoundException(BusinessException):
    """Raised when a resource is not found."""
    def __init__(self, resource: str, identifier: str = None):
        if identifier:
            detail = f"{resource} med ID {identifier} blev ikke fundet."
        else:
            detail = f"{resource} blev ikke fundet."
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class DuplicateException(BusinessException):
    """Raised when trying to create a duplicate resource."""
    def __init__(self, resource: str, field: str = None):
        if field:
            detail = f"{resource} med denne {field} eksisterer allerede."
        else:
            detail = f"{resource} eksisterer allerede."
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)


class UnauthorizedException(BusinessException):
    """Raised when user is not authorized."""
    def __init__(self, detail: str = "Ikke autoriseret."):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)

