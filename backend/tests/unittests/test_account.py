import pytest
from pydantic import ValidationError
from backend.shared.schemas.account import AccountCreate

#Account Name Boundary Value Tests

# 1. Lower Boundary (N-1) - INVALID (Handled by min_length=1)
#def test_name_min_length_below_boundary_invalid():
    # ACT & ASSERT
#    with pytest.raises(ValidationError):
#        AccountCreate(name="", saldo=100.0)


# 1. Lower Boundary (N-1) - INVALID (Handled by min_length=1)
def test_name_min_length_below_boundary_invalid():
    # ARRANGE: Define required fields with valid values
    required_user_id = 1 
    
    # ACT & ASSERT
    # We must include the required User_idUser field
    with pytest.raises(ValidationError):
        AccountCreate(
            name="", # <--- This is the field under test
            saldo=100.0,
            User_idUser=required_user_id # <--- Added required field
        )


