# backend/tests/test_bva_additional_models.py
"""
BVA tests for User, PlannedTransactions, og AccountGroups
"""

from datetime import date, timedelta

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
# ACCOUNT GROUP BVA TESTS (4.7)
# ============================================================================


def test_account_group_name_boundary():
    """BVA: Group name længde grænseværdier: 0, 1, 30, 31"""
    from backend.account.application.dto import AccountGroupsCreate

    # 0 chars - INVALID
    with pytest.raises(ValidationError):
        AccountGroupsCreate(name="", max_users=20)

    # 1 char - VALID (grænse)
    valid = AccountGroupsCreate(name="A", max_users=20)
    assert len(valid.name) == 1

    # 30 chars - VALID (grænse)
    valid = AccountGroupsCreate(name="A" * 30, max_users=20)
    assert len(valid.name) == 30

    # 31 chars - INVALID
    with pytest.raises(ValidationError):
        AccountGroupsCreate(name="A" * 31, max_users=20)


def test_account_group_max_users_boundary():
    """BVA: max_users grænseværdier: 19 (valid), 20 (valid/grænse), 21 (invalid)"""
    from backend.account.application.dto import AccountGroupsCreate

    # 19 - VALID (under grænse)
    valid = AccountGroupsCreate(name="Test", max_users=19)
    assert valid.max_users == 19

    # 20 - VALID (grænse)
    valid = AccountGroupsCreate(name="Test", max_users=20)
    assert valid.max_users == 20

    # 21 - INVALID (over grænse)
    with pytest.raises(ValidationError) as exc_info:
        AccountGroupsCreate(name="Test", max_users=21)
    error_msg = str(exc_info.value).lower()
    assert "less than or equal to 20" in error_msg or "cannot be greater than 20" in error_msg


def test_account_group_user_count_validation():
    """BVA: Antal brugere må ikke overstige max_users"""
    from backend.account.application.dto import AccountGroupsCreate

    # user_ids count > max_users - INVALID
    with pytest.raises(ValidationError) as exc_info:
        AccountGroupsCreate(
            name="Test",
            max_users=5,
            user_ids=[1, 2, 3, 4, 5, 6],  # 6 users > 5 max
        )
    assert "overstige" in str(exc_info.value).lower()

    # user_ids count = max_users - VALID
    valid = AccountGroupsCreate(
        name="Test",
        max_users=5,
        user_ids=[1, 2, 3, 4, 5],  # 5 users = 5 max
    )
    assert len(valid.user_ids) == 5

    # user_ids count < max_users - VALID
    valid = AccountGroupsCreate(
        name="Test",
        max_users=5,
        user_ids=[1, 2, 3],  # 3 users < 5 max
    )
    assert len(valid.user_ids) == 3


# ============================================================================
# RUN TESTS
# ============================================================================
# pytest backend/tests/test_bva_additional_models.py -v
