# backend/tests/test_bva_additional_models.py
"""
BVA tests for User, PlannedTransactions, og AccountGroups
"""

import pytest
from pydantic import ValidationError

# ============================================================================
# USER BVA TESTS (4.8)
# ============================================================================


def test_user_username_boundary_values():
    """BVA: Username grænseværdier: 2 (invalid), 3 (valid), 20 (valid), 21 (invalid)"""
    from backend.user.application.dto import UserCreate

    # 2 chars - INVALID
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(username="ab", password="ValidPass123", email="test@example.com")
    assert "at least 3 characters" in str(exc_info.value).lower()

    # 3 chars - VALID (grænse)
    valid = UserCreate(username="abc", password="ValidPass123", email="test@example.com")
    assert len(valid.username) == 3

    # 20 chars - VALID (grænse)
    valid = UserCreate(username="a" * 20, password="ValidPass123", email="test@example.com")
    assert len(valid.username) == 20

    # 21 chars - INVALID
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(username="a" * 21, password="ValidPass123", email="test@example.com")
    assert "at most 20 characters" in str(exc_info.value).lower()


def test_user_password_boundary_values():
    """BVA: Password grænseværdier: 7 (invalid), 8 (valid), 9 (valid)"""
    from backend.user.application.dto import UserCreate

    # 7 chars - INVALID
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            username="validuser",
            password="Pass123",  # 7 chars
            email="test@example.com",
        )
    assert "at least 8 characters" in str(exc_info.value).lower()

    # 8 chars - VALID (grænse)
    valid = UserCreate(
        username="validuser",
        password="Pass1234",  # 8 chars
        email="test@example.com",
    )
    assert len(valid.password) >= 8

    # 9 chars - VALID
    valid = UserCreate(
        username="validuser",
        password="Pass12345",  # 9 chars
        email="test@example.com",
    )
    assert len(valid.password) >= 8


def test_user_username_format():
    """BVA: Username må kun indeholde alphanumeriske tegn + underscore"""
    from backend.user.application.dto import UserCreate

    # Valid formats
    for username in ["user123", "user_name", "User123", "_underscore", "123"]:
        valid = UserCreate(username=username, password="ValidPass123", email="test@example.com")
        assert valid.username == username

    # Invalid formats with special chars
    for invalid_username in ["user-name", "user.name", "user@name", "user name"]:
        with pytest.raises(ValidationError):
            UserCreate(username=invalid_username, password="ValidPass123", email="test@example.com")


def test_user_email_format():
    """BVA: Email skal være valid format"""
    from backend.user.application.dto import UserCreate

    # Valid emails
    valid = UserCreate(username="validuser", password="ValidPass123", email="test@example.com")
    assert valid.email == "test@example.com"

    # Invalid emails
    for invalid_email in ["@example.com", "test@", "testexample.com", "test..@example.com"]:
        with pytest.raises(ValidationError):
            UserCreate(username="validuser", password="ValidPass123", email=invalid_email)


# ============================================================================
# Account group BVA tests moved to account-service test suite.
