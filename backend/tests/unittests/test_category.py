import pytest
from pydantic import ValidationError
from backend.shared.schemas.category import CategoryCreate


# ARRANGE: Define the boundaries (implicit in CategoryCreate's definition)

#Category Name Boundary Value Tests

# 1. Lower Boundary (N-1) - INVALID
def test_name_min_length_below_boundary_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError):
        CategoryCreate(name="", type="income")

# 2. Lower Boundary (N) - VALID
def test_name_min_length_at_boundary_valid():
    # ARRANGE: Name length 1 (minimum valid)
    name = "A"
    
    # ACT
    valid_category = CategoryCreate(name=name, type="income")
    
    # ASSERT
    assert valid_category.name == name

# 3. Upper Boundary (M) - VALID
def test_name_max_length_at_boundary_valid():
    # ARRANGE: Name length 30 (maximum valid)
    name = "A" * 30
    
    # ACT
    valid_category = CategoryCreate(name=name, type="income")
    
    # ASSERT
    assert len(valid_category.name) == 30

# 4. Upper Boundary (M+1) - INVALID
def test_name_max_length_above_boundary_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError):
        CategoryCreate(name="A" * 31, type="income")

# Equivilence Patritioning

def test_type_valid_value_income():
    # ARRANGE: Define the valid type
    valid_type = "income"

    # ACT
    valid_category = CategoryCreate(name="Salary", type=valid_type)

    # ASSERT
    assert valid_category.type == valid_type

def test_type_valid_value_expense():
    # Arange
    valid_type = "expense"

    # ACT
    valid_category = CategoryCreate(name="Groceries", type=valid_type)

    # ASSERT
    assert valid_category.type == valid_type


def test_type_invalid_value_unknown():
    # ARRANGE: Define an invalid type
    invalid_type = "transfer" # Neither 'income' nor 'expense'

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Type må være en af"):
        CategoryCreate(name="Invalid", type=invalid_type)


def test_type_invalid_value_case_sensitive():
    # ARRANGE: Test a case that violates strict match (e.g., uppercase)
    invalid_type = "Income"

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Type må være en af"):
        CategoryCreate(name="Invalid Case", type=invalid_type)