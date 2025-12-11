import pytest
from pydantic import ValidationError
from backend.shared.schemas.account import AccountCreate
from backend.shared.schemas.account import AccountBase

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
    # ARRANGE
    name = "A" * 30
    
    # ACT
    valid_account = AccountBase(name=name, saldo=100.0)
    
    # ASSERT
    assert len(valid_account.name) == 30

# Upper Boundary (M+1) - INVALID (31 chars)
def test_base_name_max_length_above_boundary_invalid():
        # ACT & ASSERT
    with pytest.raises(ValidationError):
        AccountBase(name="A" * 31, saldo=100.0)

# Name Content Validation

# Name Content - Whitespace Only - INVALID
def test_base_name_whitespace_only_invalid():
    with pytest.raises(ValueError, match="Account name må ikke være tomt"):
        AccountBase(name="   ", saldo=100.0)


# Name Content - Leading/Trailing Whitespace - VALID (and stripped)
def test_base_name_whitespace_stripped_valid():
    input_name = " My Account "
    expected_name = "My Account"
    valid_account = AccountBase(name=input_name, saldo=100.0)
    assert valid_account.name == expected_name

#Saldo/Balance Validation

# Saldo - Standard Rounding UP
def test_base_saldo_rounding_up():
    input_saldo = 123.456
    expected_saldo = 123.46
    account = AccountBase(name="Test", saldo=input_saldo)
    assert account.saldo == expected_saldo

# Saldo - Negative Value
def test_base_saldo_negative_value():
    input_saldo = -50.783
    expected_saldo = -50.78
    account = AccountBase(name="Test", saldo=input_saldo)
    assert account.saldo == expected_saldo



# AccountCreate Must have a User ID
REQUIRED_USER_ID = 1

# User ID - Missing Field - INVALID (Focus on AccountCreate's unique requirement)
def test_create_missing_user_id_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError) as excinfo:
        # Omitting the required User_idUser field
        AccountCreate(name="Checking", saldo=100.0)
    
    assert "User_idUser" in str(excinfo.value)

# User ID - Valid Positive Integer - VALID
def test_create_user_id_valid():
    valid_id = 5
    account = AccountCreate(name="Savings", saldo=100.0, User_idUser=valid_id)
    assert account.User_idUser == valid_id

# --- B. Inheritance Confirmation ---

# Inheritance Check - Name Max Length (Confirming AccountBase logic is inherited)
def test_create_inheritance_name_max_length_invalid():
    # ACT & ASSERT
    # This confirms that the max_length=30 logic from AccountBase is active in AccountCreate
    with pytest.raises(ValidationError):
        AccountCreate(name="A" * 31, saldo=100.0, User_idUser=REQUIRED_USER_ID)