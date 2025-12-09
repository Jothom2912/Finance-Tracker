# backend/shared/exceptions/__init__.py
"""
Business Exceptions
"""
from .business_exceptions import (
    BusinessException,
    ValidationException,
    NotFoundException,
    DuplicateException,
    UnauthorizedException
)

__all__ = [
    'BusinessException',
    'ValidationException',
    'NotFoundException',
    'DuplicateException',
    'UnauthorizedException'
]

