import pytest
from pydantic import ValidationError
from backend.shared.schemas.category import CategoryCreate # Assume this is your actual import

# ARRANGE: Define the boundaries (implicit in CategoryCreate's definition)

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

# Optional: You could combine the two valid cases for efficiency if desired
@pytest.mark.parametrize("name", ["A", "A" * 30])
def test_name_valid_boundaries(name):
    # ACT
    valid_category = CategoryCreate(name=name, type="income")
    # ASSERT
    assert valid_category.name == name