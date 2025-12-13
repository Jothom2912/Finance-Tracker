import pytest
from pydantic import ValidationError
from backend.shared.schemas.account_groups import (
    AccountGroupsBase,
    AccountGroupsCreate,
)
from backend.validation_boundaries import ACCOUNT_GROUP_BVA


# Helper Constants

VALID_NAME = "Test Group"
VALID_MAX_USERS = ACCOUNT_GROUP_BVA.max_users


# AccountGroupsBase — Name Validation (BVA)

# Min Length (N-1) - INVALID (0 chars)
def test_base_name_min_length_below_boundary_invalid():
    # Arrange
    name = ""

    # Act & Assert
    with pytest.raises(ValidationError):
        AccountGroupsBase(name=name)


# Min Length (N) - VALID (1 char)
def test_base_name_min_length_at_boundary_valid():
    # Arrange
    name = "A"

    # Act
    group = AccountGroupsBase(name=name)

    # Assert
    assert group.name == name


# Max Length (M) - VALID (30 chars)
def test_base_name_max_length_at_boundary_valid():
    # Arrange
    name = "A" * ACCOUNT_GROUP_BVA.name_max_length

    # Act
    group = AccountGroupsBase(name=name)

    # Assert
    assert len(group.name) == ACCOUNT_GROUP_BVA.name_max_length


# Max Length (M+1) - INVALID (31 chars)
def test_base_name_max_length_above_boundary_invalid():
    # Arrange
    name = "A" * (ACCOUNT_GROUP_BVA.name_max_length + 1)

    # Act & Assert
    with pytest.raises(ValidationError):
        AccountGroupsBase(name=name)


# Whitespace Only - INVALID
def test_base_name_whitespace_only_invalid():
    # Arrange
    name = "   "

    # Act & Assert
    with pytest.raises(ValueError, match="Group name må ikke være tomt"):
        AccountGroupsBase(name=name)


# Leading / Trailing Whitespace - VALID (and stripped)
def test_base_name_whitespace_stripped_valid():
    # Arrange
    input_name = "  My Group  "
    expected_name = "My Group"

    # Act
    group = AccountGroupsBase(name=input_name)

    # Assert
    assert group.name == expected_name


# AccountGroupsBase — max_users Validation (BVA)

def test_base_max_users_below_boundary_invalid():
    # Arrange
    max_users = 0

    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        AccountGroupsBase(name=VALID_NAME, max_users=max_users)

    assert "greater than or equal to 1" in str(excinfo.value)



# Lower Boundary (N) - VALID (1)
def test_base_max_users_at_lower_boundary_valid():
    # Arrange
    max_users = 1

    # Act
    group = AccountGroupsBase(name=VALID_NAME, max_users=max_users)

    # Assert
    assert group.max_users == max_users


# Upper Boundary (M) - VALID (ACCOUNT_GROUP_BVA.max_users)
def test_base_max_users_at_upper_boundary_valid():
    # Arrange
    max_users = ACCOUNT_GROUP_BVA.max_users

    # Act
    group = AccountGroupsBase(name=VALID_NAME, max_users=max_users)

    # Assert
    assert group.max_users == max_users


# Upper Boundary (M+1) - INVALID
def test_base_max_users_above_boundary_invalid():
    # Arrange
    max_users = ACCOUNT_GROUP_BVA.max_users + 1

    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        AccountGroupsBase(name=VALID_NAME, max_users=max_users)

    assert "less than or equal to" in str(excinfo.value)



# AccountGroupsCreate — user_ids Validation

# Default user_ids - VALID (empty list)
def test_create_user_ids_default_empty_valid():
    # Act
    group = AccountGroupsCreate(name=VALID_NAME)

    # Assert
    assert group.user_ids == []


# user_ids count == max_users - VALID
def test_create_user_ids_equal_to_max_users_valid():
    # Arrange
    max_users = 3
    user_ids = [1, 2, 3]

    # Act
    group = AccountGroupsCreate(
        name=VALID_NAME,
        max_users=max_users,
        user_ids=user_ids,
    )

    # Assert
    assert len(group.user_ids) == max_users


# user_ids count > max_users - INVALID
def test_create_user_ids_above_max_users_invalid():
    # Arrange
    max_users = 2
    user_ids = [1, 2, 3]

    # Act & Assert
    with pytest.raises(ValueError, match="Antal brugere"):
        AccountGroupsCreate(
            name=VALID_NAME,
            max_users=max_users,
            user_ids=user_ids,
        )


# Inheritance Checks

# Inheritance Check - Name Max Length
def test_create_inheritance_name_max_length_invalid():
    # Arrange
    name = "A" * (ACCOUNT_GROUP_BVA.name_max_length + 1)

    # Act & Assert
    with pytest.raises(ValidationError):
        AccountGroupsCreate(name=name)


# Inheritance Check - max_users Boundary
def test_create_inheritance_max_users_above_boundary_invalid():
    # Arrange
    max_users = ACCOUNT_GROUP_BVA.max_users + 1

    # Act & Assert
    with pytest.raises(ValueError):
        AccountGroupsCreate(name=VALID_NAME, max_users=max_users)
