import pytest
from pydantic import ValidationError
from backend.shared.schemas.account import AccountCreate, AccountBase


#Account Name Length Boundary Value Analysis


# Lower Boundary (N-1) - INVALID (0 chars)
def test_base_name_min_length_below_boundary_invalid():
    # ACT & ASSERT
    
    with pytest.raises(ValidationError):
        AccountBase(name="", saldo=100.0)


# Lower Boundary (N) - VALID (1 char)
def test_base_name_min_length_at_boundary_valid():
    # ARRANGE
    name = "A"
    
    # ACT
    valid_account = AccountBase(name=name, saldo=100.0)
    
    # ASSERT
    assert valid_account.name == name



# Upper Boundary (M) - VALID (30 chars)
def test_base_name_max_length_at_boundary_valid():
    # Arrange
    name = "A" * 30

    # Act
    valid_account = AccountBase(name=name, saldo=100.0)

    # Assert
    assert len(valid_account.name) == 30


# Upper Boundary (M+1) - INVALID (31 chars)
def test_base_name_max_length_above_boundary_invalid():
    # Arrange
    name = "A" * 31

    # Act & Assert
    with pytest.raises(ValidationError):
        AccountBase(name=name, saldo=100.0)

# Name Content Validation

# Whitespace Only - INVALID
def test_base_name_whitespace_only_invalid():
    # Arrange
    name = "   "

    # Act & Assert
    with pytest.raises(ValueError, match="Account name må ikke være tomt"):
        AccountBase(name=name, saldo=100.0)


# Leading/Trailing Whitespace - VALID (and stripped)
def test_base_name_whitespace_stripped_valid():
    # Arrange
    input_name = " My Account "
    expected_name = "My Account"

    # Act
    valid_account = AccountBase(name=input_name, saldo=100.0)

    # Assert
    assert valid_account.name == expected_name


#Saldo/Balance Validation

# Rounding Up
def test_base_saldo_rounding_up():
    # Arrange
    input_saldo = 123.456
    expected_saldo = 123.46

    # Act
    account = AccountBase(name="Test", saldo=input_saldo)

    # Assert
    assert account.saldo == expected_saldo


# Negative Value Rounding
def test_base_saldo_negative_value():
    # Arrange
    input_saldo = -50.783
    expected_saldo = -50.78

    # Act
    account = AccountBase(name="Test", saldo=input_saldo)

    # Assert
    assert account.saldo == expected_saldo



# AccountCreate. Must have a User ID
REQUIRED_USER_ID = 1

# Missing User ID - INVALID
def test_create_missing_user_id_invalid():
    # Arrange
    name = "Checking"
    saldo = 100.0

    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        AccountCreate(name=name, saldo=saldo)

    # Assert
    assert "User_idUser" in str(excinfo.value)


# Valid User ID - VALID
def test_create_user_id_valid():
    # Arrange
    valid_id = 5

    # Act
    account = AccountCreate(name="Savings", saldo=100.0, User_idUser=valid_id)

    # Assert
    assert account.User_idUser == valid_id


# Inheritance Confirmation 

def test_create_inheritance_name_max_length_invalid():
    # Arrange
    name = "A" * 31

    # Act & Assert
    with pytest.raises(ValidationError):
        AccountCreate(name=name, saldo=100.0, User_idUser=REQUIRED_USER_ID)
