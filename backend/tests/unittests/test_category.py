import pytest
from pydantic import ValidationError
from backend.shared.schemas.category import CategoryCreate


# Category Name Boundary Value Tests

# Lower Boundary (N-1) - INVALID
def test_name_min_length_below_boundary_invalid():
    # Arrange
    name = ""
    category_type = "income"

    # Act & Assert
    with pytest.raises(ValidationError):
        CategoryCreate(name=name, type=category_type)

# Lower Boundary (N) - VALID
def test_name_min_length_at_boundary_valid():
    # Arrange
    name = "A"
    category_type = "income"

    # Act
    valid_category = CategoryCreate(name=name, type=category_type)

    # Assert
    assert valid_category.name == name

# Upper Boundary (M) - VALID
def test_name_max_length_at_boundary_valid():
    # ARRANGE: Name length 30 (maximum valid)
    name = "A" * 30
    
    # ACT
    valid_category = CategoryCreate(name=name, type="income")
    
    # ASSERT
    assert len(valid_category.name) == 30

# Upper Boundary (M+1) - INVALID
def test_name_max_length_above_boundary_invalid():
    # Arrange
    name = "A" * 31
    category_type = "income"

    # Act & Assert
    with pytest.raises(ValidationError):
        CategoryCreate(name=name, type=category_type)

# Type Field Validation (Equivalence Partitioning)

# Valid Type: income
def test_type_valid_value_income():
    # Arrange
    valid_type = "income"

    # Act
    valid_category = CategoryCreate(name="Salary", type=valid_type)

    # Assert
    assert valid_category.type == valid_type

# Valid Type: expense
def test_type_valid_value_expense():
    # Arrange
    valid_type = "expense"

    # Act
    valid_category = CategoryCreate(name="Groceries", type=valid_type)

    # Assert
    assert valid_category.type == valid_type


# Invalid Type: unknown
def test_type_invalid_value_unknown():
    # Arrange
    invalid_type = "transfer"  # Neither 'income' nor 'expense'

    # Act & Assert
    with pytest.raises(ValueError, match="Type må være en af"):
        CategoryCreate(name="Invalid", type=invalid_type)


# Invalid Type: case sensitive violation
def test_type_invalid_value_case_sensitive():
    # Arrange
    invalid_type = "Income"  # Uppercase should fail

    # Act & Assert
    with pytest.raises(ValueError, match="Type må være en af"):
        CategoryCreate(name="Invalid Case", type=invalid_type)
